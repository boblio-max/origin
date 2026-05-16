import_name = "speedtest"
target_filename = f"{import_name}.or"
found_code = None


with open("output.txt", "r", encoding="utf-8") as f:
    content = f.read()

sections = content.split("=" * 40)
for i, section in enumerate(sections):
    if target_filename in section:
        found_code = sections[i + 1].strip()
        