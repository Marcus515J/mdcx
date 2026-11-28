from jinja2 import Environment, StrictUndefined, meta, nodes
from jinja2.sandbox import SandboxedEnvironment

_ENV: Environment = SandboxedEnvironment(
    autoescape=False,
    trim_blocks=False,
    lstrip_blocks=False,
    undefined=StrictUndefined,
)


def render_template(template: str, values: dict[str, str]) -> str:
    """使用标准 Jinja2 语法渲染命名模板。"""

    return _ENV.from_string(str(template or "")).render(**values)


def collect_template_fields(template: str, *, last_path_segment: bool = False) -> set[str]:
    ast = _ENV.parse(str(template or ""))
    fields = set() if last_path_segment else set(meta.find_undeclared_variables(ast))
    for node in ast.find_all((nodes.Name, nodes.TemplateData, nodes.Getattr, nodes.Getitem)):
        if isinstance(node, nodes.TemplateData):
            if last_path_segment and "/" in node.data:
                fields.clear()
            continue
        if isinstance(node, nodes.Name):
            if node.ctx == "load":
                fields.add(node.name)
            continue
        if isinstance(node.node, nodes.Name) and node.node.name == "fields":
            if isinstance(node, nodes.Getattr):
                fields.add(node.attr)
            elif isinstance(node.arg, nodes.Const) and isinstance(node.arg.value, str):
                fields.add(node.arg.value)
    return fields
