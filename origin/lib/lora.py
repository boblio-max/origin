from peft import LoraConfig
class lora:
    def __init__(self):
        pass
    
    def init(self, r:int, lora_alpha:int, target_modules:list, lora_dropout: float, bias:str, task_type:str):
        self.lora_config = LoraConfig(
            r=r, 
            lora_alpha=lora_alpha, 
            target_modules=target_modules, 
            lora_dropout=lora_dropout, 
            bias=bias, 
            task_type=task_type
        )
    
    def __repr__(self):
        return self.lora_config