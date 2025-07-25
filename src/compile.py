import os, Data, shutil

print(f"## Compiling Eklips project {Data.game_name}")
print(f" ~ Modifying project values to support resource")
is_loadable = open("SpecialIsResourceDataLoadable.py").read()
with open("SpecialIsResourceDataLoadable.py", "w") as f:
    f.write("# Auto-generated by compiler\nIS_IT = 1")

print(f" ~ Compiling Eklips build")
shutil.rmtree("dist", ignore_errors=1)
os.system("pyinstaller Eklips.spec")
print(f" ~ Copying project folder")
shutil.copytree(Data.data_directory, f"dist/Eklips/{Data.data_directory}")

print(f" ~ Modifying project values back to usual")
with open("SpecialIsResourceDataLoadable.py", "w") as f:
    f.write(is_loadable)