import os
from typing import Optional, Dict, Any, List
from .request_handler_factory import RequestHandlerFactory
from .config import BASE_URL
from pydantic import BaseModel, Field


class CodeGenerator:
    def __init__(self, spec: Dict[str, Any], output_dir: str = "generated_client"):
        self.spec = spec
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def generate_code(self):
        for path, path_item in self.spec.get("paths", {}).items():
            nested_class_hierarchy = self._generate_nested_class_hierarchy(
                path, path_item
            )
            for class_name, class_code in nested_class_hierarchy.items():
                self._write_to_file(f"{class_name}.py", class_code)

        self._generate_init_file()

    def _generate_nested_class_hierarchy(self, path: str, path_item: Dict[str, Any]):
        path_segments = path.strip("/").split("/")
        methods = [
            self._generate_method(http_method, path, op_details)
            for http_method, op_details in path_item.items()
        ]

        class_code = ""
        indent = ""
        class_name_hierarchy = []
        for segment in path_segments:
            class_name = self._convert_to_class_name(segment)
            class_name_hierarchy.append(class_name)
            class_code += f"{indent}class {class_name}:\n"
            class_code += f"{indent}    def __init__(self, client):\n"
            class_code += f"{indent}        self.client = client\n"
            class_code += (
                f"{indent}        self.factory = RequestHandlerFactory(client)\n\n"
            )
            indent += "    "

        full_class_name = ".".join(class_name_hierarchy)
        for method_code in methods:
            class_code += indent + method_code + "\n"

        return {full_class_name: class_code}

    def _generate_method(self, http_method: str, path: str, operation: Dict[str, Any]):
        method_name = self._generate_method_name(
            operation.get("operationId", path), http_method
        )
        params_code, params_list, body_params = self._generate_params_code(
            operation.get("parameters", []), operation.get("requestBody")
        )
        response_model = self._generate_response_model(operation.get("responses", {}))

        method_code = f"def {method_name}(self, {params_code}):\n"
        method_code += f"        \"\"\"\n        {operation.get('summary', '')}\n\n"
        method_code += f"        :param path: {path}\n"
        for param in params_list:
            method_code += f"        :param {param['name']}: {param['description']}\n"
        method_code += '        :return: The response from the API.\n        """\n'

        method_code += f"        path = '{path}'\n"
        for param in params_list:
            if param["in"] == "path":
                method_code += f"        path = path.replace('{{{{{param['name']}}}}}', str({param['name']}))\n"

        if body_params:
            method_code += "        body = {"
            for param in body_params:
                method_code += f"'{param['name']}': {param['name']}, "
            method_code = method_code.rstrip(", ")
            method_code += "}\n"
            method_code += (
                "        body = {k: v for k, v in body.items() if v is not None}\n"
            )
        else:
            method_code += "        body = None\n"

        method_code += "        headers = {}\n"
        if operation.get("requestBody"):
            for content_type in operation["requestBody"]["content"]:
                if content_type == "application/json":
                    method_code += (
                        "        headers['Content-Type'] = 'application/json'\n"
                    )
                elif content_type == "multipart/form-data":
                    method_code += (
                        "        headers['Content-Type'] = 'multipart/form-data'\n"
                    )

        if any(p["in"] == "query" for p in params_list):
            query_params = ", ".join(
                [
                    f"'{param['name']}': {param['name']}"
                    for param in params_list
                    if param["in"] == "query"
                ]
            )
            method_code += f"        params = {{ {query_params} }}\n"
            method_code += (
                "        params = {k: v for k, v in params.items() if v is not None}\n"
            )
        else:
            method_code += "        params = None\n"

        method_code += "        factory = RequestHandlerFactory(self.client)\n"
        method_code += f"        handler = factory.get_handler('{http_method.upper()}', headers.get('Content-Type'))\n"

        if response_model:
            method_code += f"        response_model = {response_model}\n"
        else:
            method_code += "        response_model = None\n"

        method_code += "        return handler.make_request(\n"
        method_code += "            path,\n"
        method_code += "            headers=headers,\n"
        method_code += "            params=params,\n"
        method_code += "            body=body,\n"
        method_code += "            response_model=response_model\n"
        method_code += "        )\n"

        return method_code

    def _generate_params_code(
        self, parameters: List[Dict[str, Any]], request_body: Optional[Dict[str, Any]]
    ):
        params_code = []
        params_list = []
        body_params = []
        for param in parameters:
            param_name = param["name"]
            param_in = param["in"]
            required = param.get("required", False)
            param_type = self._get_param_type(param)
            param_desc = param.get("description", "")
            params_list.append(
                {"name": param_name, "in": param_in, "description": param_desc}
            )
            annotation = (
                f": {param_type}" if required else f": Optional[{param_type}] = None"
            )
            params_code.append(f"{param_name}{annotation}")

        if request_body:
            for prop_name, prop_details in request_body["content"]["application/json"][
                "schema"
            ]["properties"].items():
                param_type = self._get_param_type(prop_details)
                required = prop_name in request_body["content"]["application/json"][
                    "schema"
                ].get("required", [])
                annotation = (
                    f": {param_type}"
                    if required
                    else f": Optional[{param_type}] = None"
                )
                params_code.append(f"{prop_name}{annotation}")
                body_params.append({"name": prop_name, "type": param_type})

        return ", ".join(params_code), params_list, body_params

    def _generate_response_model(self, responses: Dict[str, Any]):
        for status_code, response in responses.items():
            if "application/json" in response["content"]:
                schema = response["content"]["application/json"]["schema"]
                return self._create_model_class(schema)
        return None

    def _create_model_class(self, schema: Dict[str, Any]):
        class_name = "ResponseModel"
        model_code = f"class {class_name}(BaseModel):\n"
        for prop_name, prop_details in schema["properties"].items():
            prop_type = self._get_param_type(prop_details)
            required = prop_name in schema.get("required", [])
            default_value = "..." if required else "None"
            model_code += f"    {prop_name}: {prop_type} = Field({default_value})\n"
        self._write_to_file(f"{class_name.lower()}.py", model_code)
        return class_name

    @staticmethod
    def _get_param_type(param: Dict[str, Any]):
        param_type = param.get("type", "string")
        type_mapping = {
            "string": "str",
            "integer": "int",
            "boolean": "bool",
            "array": "list",
            "object": "Dict[str, Any]",
        }
        return type_mapping.get(param_type, "Any")

    @staticmethod
    def _convert_to_class_name(segment: str):
        return "".join(word.capitalize() for word in segment.split("_"))

    @staticmethod
    def _generate_method_name(operation_id: Optional[str], http_method: str):
        return operation_id or http_method.lower()

    def _generate_init_file(self):
        init_contents = ["from .apiclient_base import APIClientBase"]
        for path, _ in self.spec.get("paths", {}).items():
            class_name = self._convert_to_class_name(path.strip("/").split("/")[0])
            init_contents.append(f"from .{class_name} import {class_name}")
        init_content = "\n".join(init_contents) + "\n"
        self._write_to_file("__init__.py", init_content)

    def _write_to_file(self, filename: str, content: str):
        with open(os.path.join(self.output_dir, filename), "w") as file:
            file.write(content)
