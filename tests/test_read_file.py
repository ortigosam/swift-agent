from infrastructure.tools.read_file import read_file


result = read_file.invoke(
    {
        "path": "main.py",
    }
)

print(result)