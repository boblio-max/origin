import transformers as trs
import torch as th
import json as j
import os


class transformer:
    def __init__(self):
        self.data_path = None
        self.dataset = None
        self.model_name = None
        self.output_dir = None
        self.max_seq = 1
        self.batch_size = 1
        self.epoch = 1
        self.lr = 1e-3
        self.warmup_steps = 0
        self.weight_decay = 0.01
        self.fp16 = False
        self.eval_strategy = "epoch"
        self.train_data = None
        self.test_data = None
        self.model = None
        self.tokenizer = None
        self.args = None
        self.trainer = None
        self.device = None

    def init(self, data_path, model_name, output_dir):
        self.data_path = data_path
        self.dataset = None
        self.model_name = model_name
        self.output_dir = output_dir
        self.max_seq = 1
        self.batch_size = 1
        self.epoch = 1
        self.lr = 1e-3
        self.warmup_steps = 0
        self.weight_decay = 0.01
        self.fp16 = False
        self.eval_strategy = "epoch"
        self.train_data = None
        self.test_data = None
        self.model = None
        self.tokenizer = None
        self.args = None
        self.trainer = None
        self.device = None
        return self

    def config(self, max_seq, batch_size, epoch, lr):
        self.max_seq = max_seq
        self.batch_size = batch_size
        self.epoch = epoch
        self.lr = lr
        return self

    def set_device(self, device=None):
        if device:
            self.device = device
        elif th.cuda.is_available():
            self.device = "cuda"
        elif getattr(th.backends, "mps", None) and th.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"
        return self.device

    def set_training_options(self, warmup_steps=None, weight_decay=None, fp16=None, eval_strategy=None):
        if warmup_steps is not None:
            self.warmup_steps = warmup_steps
        if weight_decay is not None:
            self.weight_decay = weight_decay
        if fp16 is not None:
            self.fp16 = bool(fp16)
        if eval_strategy is not None:
            self.eval_strategy = eval_strategy
        return self

    def load_data(self):
        with open(self.data_path, "r", encoding="utf-8") as f:
            self.dataset = j.load(f)
        return self.dataset

    def split_data(self, test_size=0.2):
        x = int(len(self.dataset) * (1.0 - test_size))
        self.train_data = self.dataset[:x]
        self.test_data = self.dataset[x:]
        return self.train_data, self.test_data

    def set_pad_token(self):
        if self.tokenizer is None:
            raise Exception("Tokenizer is not loaded. Run load_tokens() first.")
        if self.tokenizer.pad_token is None:
            if self.tokenizer.eos_token is not None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            else:
                self.tokenizer.add_special_tokens({"pad_token": "[PAD]"})
        return self.tokenizer

    def load_tokens(self):
        self.tokenizer = trs.AutoTokenizer.from_pretrained(self.model_name)
        self.set_pad_token()
        return self.tokenizer

    def load_model(self, use_fp16=None):
        self.set_device()
        if use_fp16 is None:
            use_fp16 = self.fp16
        dtype = th.float16 if (use_fp16 and self.device == "cuda") else th.float32
        self.model = trs.AutoModelForCausalLM.from_pretrained(self.model_name, dtype=dtype)
        self.model = self.model.to(self.device)
        return self.model

    def load_model_from_dir(self, model_dir):
        self.set_device()
        self.model = trs.AutoModelForCausalLM.from_pretrained(model_dir, dtype=th.float32)
        self.model = self.model.to(self.device)
        if self.tokenizer is None:
            self.tokenizer = trs.AutoTokenizer.from_pretrained(model_dir)
            self.set_pad_token()
        return self.model

    def merge_model(self, lora_config):
        import peft as p
        if lora_config is None:
            raise Exception("Lora Config is not generated. Run lora_config = lora(param)")
        else:
            self.model = p.get_peft_model(self.model, lora_config)
            return self.model

    def save_adapter(self, adapter_dir):
        os.makedirs(adapter_dir, exist_ok=True)
        if self.model is None:
            raise Exception("No model to save an adapter from. Load and merge LoRA first.")
        self.model.save_pretrained(adapter_dir)
        if self.tokenizer is not None:
            self.tokenizer.save_pretrained(adapter_dir)
        print(f"LoRA adapter saved to {adapter_dir}")
        return adapter_dir

    def load_adapter(self, adapter_dir):
        import peft as p
        if self.model is None:
            raise Exception("No base model loaded. Run load_model() first.")
        self.model = p.PeftModel.from_pretrained(self.model, adapter_dir)
        return self.model

    def merge_unload(self):
        if self.model is None:
            raise Exception("No model loaded.")
        if hasattr(self.model, "merge_and_unload"):
            self.model = self.model.merge_and_unload()
        return self.model

    def tokenize_data(self):
        if self.tokenizer is None:
            raise Exception("Tokenizer is not loaded. Run load_tokens() first.")

        def _tokenize(example):
            if isinstance(example, dict):
                if "text" in example and example.get("text"):
                    text = str(example["text"])
                elif "instruction" in example:
                    text = f"Instruction: {example['instruction']}\nOutput: {example.get('output', '')}"
                elif "input" in example:
                    text = f"Instruction: {example['input']}\nOutput: {example.get('output', '')}"
                else:
                    text = str(example)
            else:
                text = str(example)
            enc = self.tokenizer(text, truncation=True, padding="max_length", max_length=self.max_seq)
            enc["labels"] = list(enc["input_ids"])
            return enc

        self.train_data = [_tokenize(e) for e in self.train_data]
        self.test_data = [_tokenize(e) for e in self.test_data]
        print(f"Tokenized {len(self.train_data)} train / {len(self.test_data)} test samples (max_seq={self.max_seq})")
        return self.train_data, self.test_data

    def training_args(self, gradient_accumulation, log_dir, log_steps, save_steps, save_t_limit, load_best_model, report=None):
        self.set_device()
        self.args = trs.TrainingArguments(
            output_dir=self.output_dir,
            per_device_train_batch_size=self.batch_size,
            per_device_eval_batch_size=self.batch_size,
            gradient_accumulation_steps=gradient_accumulation,
            num_train_epochs=self.epoch,
            learning_rate=self.lr,
            warmup_steps=self.warmup_steps,
            weight_decay=self.weight_decay,
            fp16=self.fp16 and self.device == "cuda",
            logging_dir=log_dir,
            logging_steps=log_steps,
            save_steps=save_steps,
            save_total_limit=save_t_limit,
            load_best_model_at_end=load_best_model,
            eval_strategy=self.eval_strategy,
            report_to=report if report is not None else "none",
        )
        return self.args

    def init_trainer(self):
        self.trainer = trs.Trainer(
            model=self.model,
            args=self.args,
            train_dataset=self.train_data,
            eval_dataset=self.test_data,
            processing_class=self.tokenizer,
        )
        return self.trainer

    def train(self):
        print("Starting training...")
        self.trainer.train()
        self.save_model()
        print(f"Training complete. Model saved to {self.output_dir}")

    def save_model(self):
        if self.model is None:
            raise Exception("No model to save. Load or merge a model first.")
        self.model.save_pretrained(self.output_dir)
        if self.tokenizer is not None:
            self.tokenizer.save_pretrained(self.output_dir)
        print(f"Model and tokenizer saved to {self.output_dir}")
        return self.output_dir

    def evaluate(self):
        if self.trainer is None:
            raise Exception("Trainer is not initialized. Run init_trainer() first.")
        return self.trainer.evaluate()

    def encode(self, text):
        if self.tokenizer is None:
            raise Exception("Tokenizer is not loaded. Run load_tokens() first.")
        return self.tokenizer.encode(text)

    def decode(self, token_ids):
        if self.tokenizer is None:
            raise Exception("Tokenizer is not loaded. Run load_tokens() first.")
        return self.tokenizer.decode(token_ids, skip_special_tokens=True)

    def generate(self, prompt, max_new_tokens=50, temperature=0.7, top_p=0.95, top_k=50, do_sample=True):
        if self.model is None:
            raise Exception("Model is not loaded. Run load_model() first.")
        if self.tokenizer is None:
            raise Exception("Tokenizer is not loaded. Run load_tokens() first.")
        if max_new_tokens is None:
            max_new_tokens = 50
        if temperature is None:
            temperature = 0.7
        if top_p is None:
            top_p = 0.95
        if top_k is None:
            top_k = 50
        if do_sample is None:
            do_sample = True
        self.model.eval()
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device or self.set_device())
        with th.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=do_sample,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

    def batch_generate(self, prompts, max_new_tokens=50):
        return [self.generate(p, max_new_tokens=max_new_tokens) for p in prompts]

    def pipeline(self, prompt, max_new_tokens=50):
        if self.tokenizer is None:
            self.load_tokens()
        if self.model is None:
            self.load_model()
        return self.generate(prompt, max_new_tokens=max_new_tokens)

    def param_count(self):
        if self.model is None:
            raise Exception("Model is not loaded.")
        total = sum(p.numel() for p in self.model.parameters())
        trainable = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        return total, trainable

    def run_pipeline(self, lora_config=None, gradient_accumulation=1, log_dir=None, log_steps=10,
                     save_steps=500, save_t_limit=2, load_best_model=False):
        if self.data_path is None or self.model_name is None or self.output_dir is None:
            raise Exception("Transformer is not initialized. Run init(data_path, model_name, output_dir).")
        print("=== Transformer pipeline ===")
        self.load_data()
        print(f"Loaded {len(self.dataset)} samples from {self.data_path}")
        self.split_data()
        print(f"Split -> {len(self.train_data)} train / {len(self.test_data)} test")
        self.load_tokens()
        print(f"Loaded tokenizer: {self.model_name}")
        self.load_model()
        print(f"Loaded model: {self.model_name} on {self.device}")
        if lora_config is not None:
            self.merge_model(lora_config)
            print("LoRA applied")
        self.tokenize_data()
        self.training_args(gradient_accumulation, log_dir, log_steps, save_steps, save_t_limit, load_best_model)
        self.init_trainer()
        self.train()
        print("=== Pipeline complete ===")
