import re
import sys
import os

class Route2ModuleTransformer:
    def __init__(self):
        self.express_const = ""
        self.grouped_routes = {}
        self.global_middlewares = []
        self.route_middleware = {}

    def extract_express_const(self, line:str):
        splitted_line = line.split(" ")

        if len(splitted_line) == 4 and (splitted_line[3] == "express()" or splitted_line[3] == "express();"):
            self.express_const = splitted_line[1]
        elif len(splitted_line) == 2 and ("=" and ("express()" or "express();")) in splitted_line[1]:
            splitted_line = splitted_line[1].split("=")
            self.express_const = splitted_line[0]



    def extract_route_info(self, lines, start_index):
        """Extract HTTP method, route path, and middleware from Express route definition"""
        # Match patterns like: app.get("/path", middleware, (req,res) => {
        # or: app.post('/path/:id', checkAuth, async (req,res) => {
        line = lines[start_index]
        route_pattern = rf'{self.express_const}\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']'
        match = re.search(route_pattern, line)
        
        if match:
            method = match.group(1)
            path = match.group(2)
            
            # Get the complete route definition (may span multiple lines)
            complete_route = self.get_complete_route_definition(lines, start_index)
            
            # Extract middleware from the complete route
            middleware = self.extract_middleware_from_line(complete_route)
            
            return method, path, middleware
        return None, None, []
    
    def get_complete_route_definition(self, lines, start_index):
        """Get the complete route definition that may span multiple lines"""
        complete_route = ""
        paren_count = 0
        brace_count = 0
        in_string = False
        string_char = None
        
        for i in range(start_index, len(lines)):
            line = lines[i]
            
            for char in line:
                # Handle string literals
                if char in ['"', "'"] and not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char and in_string:
                    in_string = False
                    string_char = None
                elif in_string:
                    continue
                
                # Count parentheses and braces outside of strings
                if char == '(':
                    paren_count += 1
                elif char == ')':
                    paren_count -= 1
                elif char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
            
            complete_route += line
            if i < len(lines) - 1:  # Add newline except for last line
                complete_route += "\n"
            
            # If we've closed all parentheses from the route definition, we're done
            if paren_count == 0 and i > start_index:
                break
                
        return complete_route
    def extract_middleware_from_line(self, route_text):
        """Extract middleware function names and calls (with parameters) from a route definition"""
        middleware_items = []
        
        # Pattern to match everything after the path until the route handler
        route_pattern = r'app\.(get|post|put|delete|patch)\s*\(\s*["\'][^"\']+["\']\s*,\s*(.+)'
        match = re.search(route_pattern, route_text, re.DOTALL)
        
        if match:
            # Get everything after the path
            after_path = match.group(2)
            
            # Split by commas but be careful with nested parentheses and objects
            parts = self.split_respecting_parentheses_and_objects(after_path)
            
            # Filter out the actual route handler (function/arrow function)
            for part in parts:
                part = part.strip()
                # Skip if it's the route handler (contains => or function keyword)
                if '=>' in part or part.startswith('function') or part.startswith('(req') or part.startswith('async'):
                    break
                # Skip if it's just closing parentheses/braces
                if re.match(r'^[\)\}\s]*$', part):
                    continue
                
                # For middleware with parameters, preserve the entire call
                if '(' in part:
                    # Find the complete middleware call by balancing parentheses
                    complete_call = self.extract_complete_middleware_call(after_path, part)
                    if complete_call:
                        middleware_items.append(complete_call)
                        # Skip processing other parts that are part of this call
                        break
                else:
                    # Extract simple middleware name
                    middleware_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)', part)
                    if middleware_match:
                        middleware_name = middleware_match.group(1)
                        middleware_items.append(middleware_name)
        
        return middleware_items
    
    def extract_complete_middleware_call(self, full_text, starting_part):
        """Extract complete middleware call with all parameters"""
        # Find where this middleware starts in the full text
        start_idx = full_text.find(starting_part.split('(')[0])
        if start_idx == -1:
            return starting_part
        
        # Extract from the start of middleware name to the end of its parameters
        paren_count = 0
        brace_count = 0
        in_string = False
        string_char = None
        result = ""
        
        i = start_idx
        while i < len(full_text):
            char = full_text[i]
            
            # Handle string literals
            if char in ['"', "'"] and not in_string:
                in_string = True
                string_char = char
            elif char == string_char and in_string:
                in_string = False
                string_char = None
            elif in_string:
                result += char
                i += 1
                continue
            
            # Handle nesting outside of strings
            if char == '(':
                paren_count += 1
            elif char == ')':
                paren_count -= 1
                result += char
                if paren_count == 0:
                    # Complete middleware call found
                    break
            elif char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
            elif char == ',' and paren_count == 0 and brace_count == 0:
                # End of this middleware, don't include the comma
                break
            
            result += char
            i += 1
        
        return result.strip()
    
    def split_respecting_parentheses_and_objects(self, text):
        """Split text by commas while respecting parentheses and object literal nesting"""
        parts = []
        current_part = ""
        paren_count = 0
        brace_count = 0
        in_string = False
        string_char = None
        
        i = 0
        while i < len(text):
            char = text[i]
            
            # Handle string literals
            if char in ['"', "'"] and not in_string:
                in_string = True
                string_char = char
            elif char == string_char and in_string:
                in_string = False
                string_char = None
            elif in_string:
                current_part += char
                i += 1
                continue
            
            # Handle nesting outside of strings
            if char == '(':
                paren_count += 1
            elif char == ')':
                paren_count -= 1
            elif char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
            elif char == ',' and paren_count == 0 and brace_count == 0:
                parts.append(current_part.strip())
                current_part = ""
                i += 1
                continue
            
            current_part += char
            i += 1
        
        # Add the last part
        if current_part.strip():
            parts.append(current_part.strip())
        
        return parts
    
    def path_to_function_name(self, path):
        """Convert route path to function name"""
        # Remove leading slash 
        func_name = path.lstrip('/')
        # Replace any character not valid in a JS identifier with an underscore
        func_name = re.sub(r'[^a-zA-Z0-9_$]', '_', func_name)
        # Convert parameter syntax (:id becomes id, :userId becomes userId)
        func_name = re.sub(r':(\w+)', r'\1', func_name)
        # Clean up multiple underscores
        func_name = re.sub(r'_+', '_', func_name)
        # Remove trailing underscore
        func_name = func_name.rstrip('_')
        
        # Handle root path
        if not func_name:
            func_name = 'index'
            
        return func_name
    
    def extract_route_params(self, path):
        """Extract route parameters like :id from path"""
        params = re.findall(r':(\w+)', path)
        return params
    
    def remove_unsupported(self, content):
        """Remove optional chaining keywords from function content"""
        content = re.sub(r'\?\.', '.', content)
        return content
    
    def has_route_handler(self, lines, start_index):
        """Check if there's an actual route handler (function with body) after middleware"""
        for i in range(start_index, len(lines)):
            line = lines[i]
            
            # Look for arrow function or regular function
            if '=>' in line or 'function' in line:
                return True
            
            # If we find a closing parenthesis without finding a handler, it's middleware-only
            if ')' in line and '=>' not in line and 'function' not in line:
                return False
                
        return False
    
    def extract_function_body(self, lines, start_index, middleware):
        """Extract the function body from the route handler"""
        body_lines = []
        brace_count = 0
        in_function = False
        found_arrow = False
        found_closing_paren = False
        
        for i in range(start_index, len(lines)):
            line = lines[i]
            
            # Look for arrow function or regular function
            if '=>' in line or 'function' in line:
                found_arrow = True
            
            # Check if this line ends the route definition (closing parenthesis)
            if not found_arrow and ')' in line:
                # This might be a middleware-only route
                found_closing_paren = True
                break
            
            # Count braces to determine when function ends
            if found_arrow:
                brace_count += line.count('{')
                brace_count -= line.count('}')
                
                if '{' in line and not in_function:
                    in_function = True
                    # Extract everything after the opening brace
                    brace_index = line.find('{')
                    if brace_index + 1 < len(line):
                        remaining = line[brace_index + 1:].strip()
                        if remaining:
                            body_lines.append(remaining)
                elif in_function:
                    if brace_count > 0:
                        body_lines.append(line)
                    else:
                        # Function ended, add everything before the closing brace
                        brace_index = line.rfind('}')
                        if brace_index > 0:
                            remaining = line[:brace_index].strip()
                            if remaining:
                                body_lines.append(remaining)
                        break
        
        # If no function body was found (middleware-only route), return empty body
        if not found_arrow and found_closing_paren:
            return [], i
        
        return body_lines, i
    
    def create_function_signature(self, func_name, route_params):
        """Create function signature based on route info"""
        params = ['method', 'req', 'res']
        
        # Add route parameters
        for param in route_params:
            params.append(param)
            
        return f"function {func_name}({', '.join(params)})"
    
    def create_method_function_signature(self, func_name, method, route_params, async_function):
        """Create method-specific function signature"""
        params = ['req', 'res']
        
        # Add route parameters
        for param in route_params:
            params.append(param)
        
        function = ""
        if (async_function):
            function = "async "
            
        return function + f"function {func_name}_{method}({', '.join(params)})"
    
    def convert_middleware_to_calls(self, middleware_items, method_func_name, route_params, has_handler):
        """Convert middleware items to function calls"""
        if not middleware_items:
            if has_handler:
                # No middleware, call method function directly
                method_params = ['req', 'res']
                method_params.extend(route_params)
                return [f"{method_func_name}({', '.join(method_params)});"]
            else:
                return ["// No middleware or handler defined"]
        
        # If there's no handler, execute the middleware directly without chaining
        if not has_handler:
            current_call = f"{middleware_items[-1]}(req, res)"
            middleware_items.pop()
        else:
            # Build the chain from right to left (innermost to outermost) when there's a handler
            method_params = ['req', 'res']
            method_params.extend(route_params)
            current_call = f"{method_func_name}({', '.join(method_params)})"

        for middleware_item in reversed(middleware_items):
            if '(' in middleware_item:
                # Middleware with parameters - use the complete call as is
                current_call = f"{middleware_item}(req, res, () => {current_call})"
            else:
                # Simple middleware name - call with req, res
                current_call = f"{middleware_item}(req, res, () => {current_call})"
        return [f"{current_call};"]
    
    def generate_function_code(self, func_info):
        """Generate the complete function code"""
        func_name = func_info['func_name']
        route_params = func_info['route_params']
        methods = func_info['methods']
        
        # Create main function signature
        signature = self.create_function_signature(func_name, route_params)
        
        # Generate function body
        lines = [f"{signature} {{"]
        lines.append("")
        
        # Add method checks in main function
        method_keys = list(methods.keys())
        method_functions_to_generate = []
        
        for i, method in enumerate(method_keys):
            middleware, body, has_handler, async_function = methods[method]
            method_func_name = f"{func_name}_{method}"
            
            if i == 0:
                lines.append(f"    if (method === \"{method}\") {{")
            else:
                lines.append(f"    else if (method === \"{method}\") {{")
            
            # Generate middleware calls or direct function call
            if has_handler:
                method_functions_to_generate.append((method, middleware, body, async_function))
            if middleware:
                middleware_calls = self.convert_middleware_to_calls(middleware, method_func_name, route_params, has_handler)
                for call in middleware_calls:
                    lines.append(f"        {call}")
            elif not middleware and has_handler:
                # No middleware, call method function directly
                method_params = ['req', 'res']
                method_params.extend(route_params)
                lines.append(f"        {method_func_name}({', '.join(method_params)});")
            
            else:
                lines.append("        // No middleware or handler defined")
        
            lines.append("    }")
        
        lines.append("")
        
        # Generate method-specific functions only for routes that have handlers
        for method, middleware, body, async_function in method_functions_to_generate:
            method_func_name = f"{func_name}_{method}"
            
            # Process body lines
            if body:  # Only add method if body exists
                # Create method function signature
                method_signature = self.create_method_function_signature(func_name, method, route_params, async_function)
                lines.append(f"    {method_signature} {{")
                for line in body:
                    if line.strip():
                        # Remove chaining operators
                        processed_line = self.remove_unsupported(line)
                        # Fix parameter references (req.params.id -> id)
                        for param in route_params:
                            processed_line = re.sub(f'req\\.params\\.{param}', param, processed_line)
                        lines.append(f"        {processed_line}")
            
            lines.append("    }")
            lines.append("")
        
        lines.append("}")
        lines.append("")
        
        return '\n'.join(lines)
    
    def create_exports(self):
        output = 'module.exports = {'
        for func_key in self.grouped_routes.keys():
            output += self.grouped_routes[func_key]["func_name"] + ', '
        output += f"{self.express_const}}}"
        return output
    
    def extract_global_middleware(self, line):
        pattern = rf'{self.express_const}\.use\((.+)\)'
        match = re.search(pattern, line.strip())
        if not match:
            return False

        raw = match.group(1)
        parts = self.split_respecting_parentheses_and_objects(raw)

        if parts and parts[0].startswith("'") or parts[0].startswith('"'):
            # Route + middleware(s)
            route = parts[0].strip("'\"")
            for p in parts[1:]:
                if p:
                    self.route_middleware.setdefault(route, []).append(p.strip())
        else:
            # Global middleware
            for p in parts:
                if p:
                    self.global_middlewares.append(p.strip())
            
        return True
        
    def get_route_prefixes(self, route: str) -> list[str]:
        """
        Given '/blog/user/list', return:
        ['/blog', '/blog/user', '/blog/user/list']
        """
        parts = [p for p in route.strip("/").split("/") if p]
        prefixes = []
        for i in range(1, len(parts) + 1):
            prefixes.append("/" + "/".join(parts[:i]))
        return prefixes
    
    def transform_file(self, input_file, output_file):
        """Transform the entire Express.js file"""
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
        except FileNotFoundError:
            print(f"Error: File '{input_file}' not found.")
            return False
        
        routes = []
        output_map = {}
        i = 0
        
        while i < len(lines):
            line = lines[i]
            if (self.express_const == ""):
                self.extract_express_const(line)

            # Updated to receive middleware as well - now pass lines and index
            method, path, middleware = self.extract_route_info(lines, i)
            
            if method and path:
                func_name = self.path_to_function_name(path)
                route_params = self.extract_route_params(path)
                
                # Check if there's an actual route handler
                has_handler = self.has_route_handler(lines, i)
                
                # Extract function body
                body_lines, end_index = self.extract_function_body(lines, i, middleware)

                async_function = False

                if ("async" in line):
                    async_function = True

                route = {
                    'method': method,
                    'path': path,
                    'func_name': func_name,
                    'route_params': route_params,
                    'middleware': middleware,
                    'body': body_lines,
                    'has_handler': has_handler,
                    'async_function': async_function,
                    'line': i
                }
                
                routes.append(route)

                i = end_index + 1
            else:
                i += 1
                if (self.extract_global_middleware(line)):
                    continue
                # Remove server creation 
                if (f"{self.express_const}.listen" in line):
                    break
                output_map[i] = self.remove_unsupported(line)

        
        # Group routes by function name and path
        for route in routes:
            func_key = f"{route['func_name']}_{route['path']}"
            if func_key not in self.grouped_routes:
                self.grouped_routes[func_key] = {
                    'func_name': route['func_name'],
                    'path': route['path'],
                    'route_params': route['route_params'],
                    'methods': {},
                    'first_line': route['line']
                }

            paths = self.get_route_prefixes(route['path'])

            # middlewares resolution
            middlewares = [
                mw
                for p in paths if p in self.route_middleware
                for mw in self.route_middleware[p]
            ]
            combined_middleware = self.global_middlewares + middlewares + route['middleware']
            self.grouped_routes[func_key]['methods'][route['method']] = [combined_middleware, route['body'], route['has_handler'], route['async_function']]
        
        # Create output mapping for routes
        for func_key, func_info in self.grouped_routes.items():
            function_code = self.generate_function_code(func_info)
            output_map[func_info['first_line']] = function_code
        
        # Sort by line number
        sorted_keys = sorted(output_map.keys())
        output_lines = [output_map[key] for key in sorted_keys]

        output_lines.append(self.create_exports())
        
        # Write output file
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(output_lines))
            print(f"Successfully transformed '{input_file}' to '{output_file}'")
            print(f"Generated functions from {len(routes)} routes")
            return True
        except Exception as e:
            print(f"Error writing output file: {e}")
            return False


class Module2AppTRansformer:
    def __init__(self, routeTransformer: Route2ModuleTransformer):
        self.grouped_routes = routeTransformer.grouped_routes
        self.express_const = routeTransformer.express_const

    def writeRoute(self, values: dict):
        routeOutput = []
        for method, items in values["methods"].items():
            routeOutput.append(f"app.{method}('{values['path']}', (req, res) => {{")
            route_line = f'\tprocessedModule.{values["func_name"]}("{method}", req, res'
            for param in values['route_params']:
                route_line += f", req.params.{param}"
            route_line += ")"
            routeOutput.append(route_line)
            routeOutput.append("})")
            routeOutput.append("")

        return routeOutput

    def transform_file(self, module_file, output_file):
        output_lines = []
        
        output_lines.append(f"const processedModule = require('./{os.path.basename(module_file)}')")
        output_lines.append(f"const app = processedModule.{self.express_const}")
        output_lines.append("")

        for _, values in self.grouped_routes.items():
            for route in self.writeRoute(values):
                output_lines.append(route)
            
        output_lines.append("app.listen(3000, '0.0.0.0')")

        # Write output file
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(output_lines))
            print(f"Successfully transformed '{module_file}' to '{output_file}'")
            return True
        except Exception as e:
            print(f"Error writing output file: {e}")
            return False



def main():
    if len(sys.argv) != 3:
        print("Usage: python3 express_transformer.py <input_file> <processed_file> <app_file>")
        print("Example: python3 express_transformer.py server.js processed.js app.js")
        sys.exit(1)
    
    input_file = sys.argv[1]
    processed_file = sys.argv[2]
    #app_file = sys.argv[3]
    
    routeTransformer = Route2ModuleTransformer()
    success = routeTransformer.transform_file(input_file, processed_file)
    # moduleTransformer = Module2AppTRansformer(routeTransformer)
    # moduleTransformer.transform_file(processed_file, app_file)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()