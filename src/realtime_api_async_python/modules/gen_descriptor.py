import inspect
from typing import get_type_hints, Any, Dict

def build_function_descriptor(func) -> Dict[str, Any]:
    """
    Creates a JSON-like function descriptor by inspecting the function's
    signature, docstring, and type annotations.

    :param func: The function object to inspect.
    :return: A dictionary representing the function descriptor in JSON schema style.
    """
    # If the function has a docstring, use it as the description
    doc = func.__doc__ or ""
    
    # Prepare the skeleton descriptor
    descriptor = {
        "type": "function",
        "name": func.__name__,
        "description": doc.strip(),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }

    # Use signature to iterate over parameters
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)

    # Simple mapping from Python types to JSON Schema types
    python_to_json_types = {
        str: "string",
        int: "number",
        float: "number",
        bool: "boolean",
        dict: "object",
        list: "array"
    }

    for param_name, param in sig.parameters.items():
        # Determine the annotated type (defaulting to str if missing)
        annotation = type_hints.get(param_name, str)
        json_type = python_to_json_types.get(annotation, "string")
        
        descriptor["parameters"]["properties"][param_name] = {
            "type": json_type,
            "description": f"Parameter '{param_name}' of type '{annotation.__name__}'."
        }
        
        # If there is no default value, consider this parameter 'required'
        if param.default is inspect._empty:
            descriptor["parameters"]["required"].append(param_name)

    return descriptor