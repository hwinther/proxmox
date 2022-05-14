# LLM tips and tricks

## Installation of llama.cpp for processing

```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp/ && make
apt install python3-pip python3-venv git-lfs
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```

## Download and convert + quantize a model

```bash
cd /mnt/storage/models
git clone https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct
# If you want to clone without large files - just their pointers
# GIT_LFS_SKIP_SMUDGE=1 git clone https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct

python3 /root/llama.cpp/convert.py ./Meta-Llama-3-8B-Instruct/ --outtype f32 --vocab-type bpe
/root/llama.cpp/quantize ./Meta-Llama-3-8B-Instruct/ggml-model-f32.gguf Meta-Llama-3-8B-Q4_K_M.gguf Q4_K_M
# see this for type https://github.com/ggerganov/llama.cpp/discussions/2094
```
