import ast
import os

def find_duplicate_classes(root_dir):
    class_map = {}  # {class_name: [file_path1, file_path2]}

    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.py'):
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            class_map.setdefault(node.name, []).append(full_path)
                except Exception as e:
                    print(f"Ошибка в файле {full_path}: {e}")

    # Выводим только дубликаты
    duplicates = {name: paths for name, paths in class_map.items() if len(paths) > 1}
    
    if not duplicates:
        print("Дубликатов имен классов не найдено.")
    else:
        print("Найдены дубликаты имен классов:")
        for name, paths in duplicates.items():
            print(f"\nКласс '{name}' встречается в:\n  " + "\n  ".join(paths))

if __name__ == "__main__":
    # Укажи путь к своему проекту
    find_duplicate_classes('.')
