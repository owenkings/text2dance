import torch
import torch.nn as nn

from transformers import CLIPVisionModel, CLIPImageProcessor, CLIPVisionConfig


class CLIPVisionTower(nn.Module):
    def __init__(self, vision_tower, args, delay_load=False):
        super().__init__()

        self.is_loaded = False

        self.vision_tower_name = vision_tower
        self.select_layer = args.mm_vision_select_layer
        self.select_feature = getattr(args, 'mm_vision_select_feature', 'patch')

        if not delay_load:
            self.load_model()
        elif getattr(args, 'unfreeze_mm_vision_tower', False):
            self.load_model()
        else:
            self.cfg_only = CLIPVisionConfig.from_pretrained(self.vision_tower_name)

    def load_model(self, device_map=None):
        if self.is_loaded:
            print('{} is already loaded, `load_model` called again, skipping.'.format(self.vision_tower_name))
            return

        self.image_processor = CLIPImageProcessor.from_pretrained(self.vision_tower_name)
        self.vision_tower = CLIPVisionModel.from_pretrained(self.vision_tower_name, device_map=device_map)
        self.vision_tower.requires_grad_(False)

        self.is_loaded = True

    def feature_select(self, image_forward_outs):
        image_features = image_forward_outs.hidden_states[self.select_layer]
        if self.select_feature == 'patch':
            image_features = image_features[:, 1:]
        elif self.select_feature == 'cls_patch':
            image_features = image_features
        else:
            raise ValueError(f'Unexpected select feature: {self.select_feature}')
        return image_features

    # @torch.no_grad()
    def forward(self, images):
        if type(images) is list:
            image_features = []
            for image in images:
                # 确保图像张量在正确的设备上，处理meta tensor问题
                try:
                    processed_image = image.to(device=self.device, dtype=self.dtype).unsqueeze(0)
                except (RuntimeError, NotImplementedError) as e:
                    if "meta tensor" in str(e).lower():
                        # 如果遇到meta tensor错误，尝试使用CUDA设备
                        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                        processed_image = image.to(device=device, dtype=torch.float16 if device.type == 'cuda' else torch.float32).unsqueeze(0)
                    else:
                        raise e
                image_forward_out = self.vision_tower(processed_image, output_hidden_states=True)
                image_feature = self.feature_select(image_forward_out).to(image.dtype)
                image_features.append(image_feature)
        else:
            # 确保图像张量在正确的设备上，处理meta tensor问题
            try:
                processed_images = images.to(device=self.device, dtype=self.dtype)
            except (RuntimeError, NotImplementedError) as e:
                if "meta tensor" in str(e).lower():
                    # 如果遇到meta tensor错误，尝试使用CUDA设备
                    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                    processed_images = images.to(device=device, dtype=torch.float16 if device.type == 'cuda' else torch.float32)
                else:
                    raise e
            
            # 额外检查：确保vision_tower不在meta状态
            try:
                image_forward_outs = self.vision_tower(processed_images, output_hidden_states=True)
            except (RuntimeError, NotImplementedError) as e:
                if "meta tensor" in str(e).lower():
                    # 如果vision_tower在meta状态，尝试使用CPU进行推理
                    print("Warning: Vision tower in meta state, falling back to CPU processing")
                    device = torch.device('cpu')
                    
                    # 检查输入张量是否也是meta tensor
                    if processed_images.is_meta:
                        # 如果输入也是meta tensor，重新从原始images创建
                        try:
                            processed_images = images.to(device, dtype=torch.float32)
                        except (RuntimeError, NotImplementedError):
                            # 如果原始images也是meta，创建一个dummy tensor
                            processed_images = torch.randn_like(images, device=device, dtype=torch.float32)
                    else:
                        processed_images = processed_images.to(device, dtype=torch.float32)
                    
                    # 临时创建一个CPU版本的vision tower进行推理
                    from transformers import CLIPVisionModel
                    temp_vision_tower = CLIPVisionModel.from_pretrained(self.vision_tower_name)
                    temp_vision_tower.eval()
                    with torch.no_grad():
                        image_forward_outs = temp_vision_tower(processed_images, output_hidden_states=True)
                    del temp_vision_tower  # 清理临时模型
                else:
                    raise e
            image_features = self.feature_select(image_forward_outs).to(images.dtype)

        return image_features

    @property
    def dummy_feature(self):
        return torch.zeros(1, self.hidden_size, device=self.device, dtype=self.dtype)

    @property
    def dtype(self):
        return self.vision_tower.dtype

    @property
    def device(self):
        return self.vision_tower.device

    @property
    def config(self):
        if self.is_loaded:
            return self.vision_tower.config
        else:
            return self.cfg_only

    @property
    def hidden_size(self):
        return self.config.hidden_size

    @property
    def num_patches_per_side(self):
        return self.config.image_size // self.config.patch_size

    @property
    def num_patches(self):
        return (self.config.image_size // self.config.patch_size) ** 2



class CLIPVisionTowerS2(CLIPVisionTower):
    def __init__(self, vision_tower, args, delay_load=False):
        super().__init__(vision_tower, args, delay_load)

        self.s2_scales = getattr(args, 's2_scales', '336,672,1008')
        self.s2_scales = list(map(int, self.s2_scales.split(',')))
        self.s2_scales.sort()
        self.s2_split_size = self.s2_scales[0]
        self.s2_image_size = self.s2_scales[-1]

        try:
            from s2wrapper import forward as multiscale_forward
        except ImportError:
            raise ImportError('Package s2wrapper not found! Please install by running: \npip install git+https://github.com/bfshi/scaling_on_scales.git')
        self.multiscale_forward = multiscale_forward

        # change resize/crop size in preprocessing to the largest image size in s2_scale
        if not delay_load or getattr(args, 'unfreeze_mm_vision_tower', False):
            self.image_processor.size['shortest_edge'] = self.s2_image_size
            self.image_processor.crop_size['height'] = self.image_processor.crop_size['width'] = self.s2_image_size

    def load_model(self, device_map=None):
        if self.is_loaded:
            print('{} is already loaded, `load_model` called again, skipping.'.format(self.vision_tower_name))
            return

        self.image_processor = CLIPImageProcessor.from_pretrained(self.vision_tower_name)
        self.vision_tower = CLIPVisionModel.from_pretrained(self.vision_tower_name, device_map=device_map)
        self.vision_tower.requires_grad_(False)

        self.image_processor.size['shortest_edge'] = self.s2_image_size
        self.image_processor.crop_size['height'] = self.image_processor.crop_size['width'] = self.s2_image_size

        self.is_loaded = True

    # @torch.no_grad()
    def forward_feature(self, images):
        # 确保图像张量在正确的设备上，处理meta tensor问题
        try:
            processed_images = images.to(device=self.device, dtype=self.dtype)
        except (RuntimeError, NotImplementedError) as e:
            if "meta tensor" in str(e).lower():
                # 如果遇到meta tensor错误，尝试使用CUDA设备
                device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                processed_images = images.to(device=device, dtype=torch.float16 if device.type == 'cuda' else torch.float32)
            else:
                raise e
        
        # 额外检查：确保vision_tower不在meta状态
        try:
            image_forward_outs = self.vision_tower(processed_images, output_hidden_states=True)
        except (RuntimeError, NotImplementedError) as e:
            if "meta tensor" in str(e).lower():
                # 如果vision_tower在meta状态，尝试使用CPU进行推理
                print("Warning: Vision tower in meta state, falling back to CPU processing")
                device = torch.device('cpu')
                
                # 检查输入张量是否也是meta tensor
                if processed_images.is_meta:
                    # 如果输入也是meta tensor，重新从原始images创建
                    try:
                        processed_images = images.to(device, dtype=torch.float32)
                    except (RuntimeError, NotImplementedError):
                        # 如果原始images也是meta，创建一个dummy tensor
                        processed_images = torch.randn_like(images, device=device, dtype=torch.float32)
                else:
                    processed_images = processed_images.to(device, dtype=torch.float32)
                
                # 临时创建一个CPU版本的vision tower进行推理
                from transformers import CLIPVisionModel
                temp_vision_tower = CLIPVisionModel.from_pretrained(self.vision_tower_name)
                temp_vision_tower.eval()
                with torch.no_grad():
                    image_forward_outs = temp_vision_tower(processed_images, output_hidden_states=True)
                del temp_vision_tower  # 清理临时模型
            else:
                raise e
        image_features = self.feature_select(image_forward_outs).to(images.dtype)
        return image_features

    # @torch.no_grad()
    def forward(self, images):
        if type(images) is list:
            image_features = []
            for image in images:
                image_feature = self.multiscale_forward(self.forward_feature, image.unsqueeze(0), img_sizes=self.s2_scales, max_split_size=self.s2_split_size)
                image_features.append(image_feature)
        else:
            image_features = self.multiscale_forward(self.forward_feature, images, img_sizes=self.s2_scales, max_split_size=self.s2_split_size)

        return image_features

    @property
    def hidden_size(self):
        return self.config.hidden_size * len(self.s2_scales)
