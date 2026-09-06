from peft import LoraConfig


class lora:
    def __init__(self):
        self.lora_config = None

    def init(self, r, lora_alpha, target_modules, lora_dropout, bias, task_type):
        self.lora_config = LoraConfig(
            r=r,
            lora_alpha=lora_alpha,
            target_modules=target_modules,
            lora_dropout=lora_dropout,
            bias=bias,
            task_type=task_type,
        )
        return self.lora_config

    def init_ext(self, r, lora_alpha, target_modules, lora_dropout, bias, task_type,
                 use_rslora=None, fan_in_fan_out=None, modules_to_save=None,
                 init_lora_weights=None, layers_to_transform=None, layers_pattern=None):
        kwargs = dict(
            r=r,
            lora_alpha=lora_alpha,
            target_modules=target_modules,
            lora_dropout=lora_dropout,
            bias=bias,
            task_type=task_type,
        )
        if use_rslora is not None:
            kwargs["use_rslora"] = use_rslora
        if fan_in_fan_out is not None:
            kwargs["fan_in_fan_out"] = fan_in_fan_out
        if modules_to_save is not None:
            kwargs["modules_to_save"] = modules_to_save
        if init_lora_weights is not None:
            kwargs["init_lora_weights"] = init_lora_weights
        if layers_to_transform is not None:
            kwargs["layers_to_transform"] = layers_to_transform
        if layers_pattern is not None:
            kwargs["layers_pattern"] = layers_pattern
        self.lora_config = LoraConfig(**kwargs)
        return self.lora_config

    def __repr__(self):
        return str(self.lora_config)


