import argparse
import re
import xml.etree.ElementTree as ET


class ParseError(Exception):
    pass


class ConfigParser:
    def __init__(self):
        self.constants = {}

    def remove_comments(self, text: str) -> str:
        return re.sub(r"=begin.*?=end", "", text, flags=re.S)

    def parse_number(self, token: str) -> int:
        if token.startswith(("0o", "0O")):
            try:
                return int(token, 8)
            except ValueError:
                pass
        raise ParseError(f"Некорректное число: {token}")

    def parse_string(self, token: str) -> str:
        m = re.fullmatch(r'@"(.*)"', token)
        if not m:
            raise ParseError(f"Некорректная строка: {token}")
        return m.group(1)

    def parse_value(self, token: str):
        token = token.strip()

        if token.startswith("?{") and token.endswith("}"):
            name = token[2:-1]
            if name not in self.constants:
                raise ParseError(f"Неизвестная константа: {name}")
            return self.constants[name]

        if token.startswith("array(") and token.endswith(")"):
            inner = token[len("array("):-1]
            return [self.parse_value(t) for t in self.split_args(inner)]

        if token.startswith("$["):
            inner = token[2:-1]
            return self.parse_dict(inner)

        if token.startswith('@'):
            return self.parse_string(token)

        if re.fullmatch(r"0[oO][0-7]+", token):
            return self.parse_number(token)

        raise ParseError(f"Неизвестное значение: {token}")

    def split_args(self, text: str):
        args = []
        current = ""
        level = 0

        for ch in text:
            if ch in "([":
                level += 1
            elif ch in ")]":
                level -= 1

            if ch == "," and level == 0:
                args.append(current.strip())
                current = ""
            else:
                current += ch

        if current.strip():
            args.append(current.strip())

        return args

    def parse_dict(self, text: str):
        result = {}
        for part in self.split_args(text):
            if ":" not in part:
                continue
            key, value = part.split(":", 1)
            result[key.strip()] = self.parse_value(value.strip())
        return result

    def parse(self, text: str):
        text = self.remove_comments(text)
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        expr_lines = []

        for line in lines:
            m = re.fullmatch(r"def\s+([A-Z_]+)\s*:=\s*(.+)", line)
            if m:
                name, value = m.groups()
                self.constants[name] = self.parse_value(value)
            else:
                expr_lines.append(line)

        if not expr_lines:
            raise ParseError("В конфигурации нет основного выражения")

        expr = " ".join(expr_lines)
        return self.parse_value(expr)

    def to_xml(self, data, root_name="config"):
        root = ET.Element(root_name)
        self.build_xml(root, data)
        return ET.ElementTree(root)

    def build_xml(self, parent, data):
        if isinstance(data, dict):
            for k, v in data.items():
                child = ET.SubElement(parent, k)
                self.build_xml(child, v)
        elif isinstance(data, list):
            for item in data:
                child = ET.SubElement(parent, "item")
                self.build_xml(child, item)
        else:
            parent.text = str(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", required=True)
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        text = f.read()

    cp = ConfigParser()
    data = cp.parse(text)
    tree = cp.to_xml(data)
    tree.write(args.output, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    main()