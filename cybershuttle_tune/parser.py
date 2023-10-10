from jinja2 import Environment, PackageLoader, meta

def parse_file(file_path):
    with open(file_path, "r") as text_file:
        template_text = text_file.read()
    e = Environment()
    ast = e.parse(template_text)
    variables = meta.find_undeclared_variables(ast)
    return variables

def apply_values(file_path, variable_values):
    with open(file_path, "r") as text_file:
        template_text = text_file.read()
    e = Environment()
    template = e.from_string(template_text)
    final_text = template.render(variable_values)
    return final_text