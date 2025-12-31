import torch
import time

def burn_gpu():
    if not torch.cuda.is_available():
        print("CUDA NOT AVAILABLE. CANNOT BURN GPU.")
        return

    print(f"Burning GPU: {torch.cuda.get_device_name(0)}")
    print("Look at Task Manager -> '3D' or 'Cuda' graph NOW!")
    
    # Large matrix multiplication loop
    a = torch.randn(10000, 10000, device="cuda", dtype=torch.float16)
    b = torch.randn(10000, 10000, device="cuda", dtype=torch.float16)
    
    start = time.time()
    while time.time() - start < 10:
        _ = torch.matmul(a, b)
        print(".", end="", flush=True)
    
    print("\nDone.")

if __name__ == "__main__":
    burn_gpu()
