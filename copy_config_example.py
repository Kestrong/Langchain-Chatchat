# 用于批量将configs下的.example文件复制并命名为.py文件
import os
import shutil
import sys


def copy_test():
    files = os.listdir("configs")
    src_files = [os.path.join("configs", file) for file in files if ".example" in file]

    for src_file in src_files:
        tar_file = src_file.replace(".example", "")
        shutil.copy(src_file, tar_file)


def copy_prod():
    files = os.listdir(os.path.join("configs", "prod"))
    for file in files:
        src_file = os.path.join(os.path.join("configs", "prod"), file)
        tar_file = os.path.join(os.path.join("configs"), file).replace(".example", "")
        shutil.copy(src_file, tar_file)


if __name__ == "__main__":
    prod = "prod" in sys.argv
    if prod:
        copy_prod()
    else:
        copy_test()
