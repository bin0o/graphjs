import re
import sys

class ExpressRouteTransformer:
    def __init__(self):
        self.functions = []
        self.current_function = None
        
    def extract_route_info(self, line):
        """Extract HTTP method, route path, and middleware from Express route definition"""
        # Match patterns like: app.get("/path", middleware, (req,res) => {
        # or: app.post('/path/:id', checkAuth, async (req,res) => {
        route_pattern = r'app\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']'
        match = re.search(route_pattern, line)
        
        if match:
            method = match.group(1)
            path = match.group(2)
            
            # Extract middleware from the same line
            middleware = self.extract_middleware_from_line(line)
            
            return method, path, middleware
        return None, None, []
    
    def extract_middleware_from_line(self, line):
        """Extract middleware function names from a route definition line"""
        middleware_names = []
        
        # Pattern to match everything after the path until the route handler
        route_pattern = r'app\.(get|post|put|delete|patch)\s*\(\s*["\'][^"\']+["\']\s*,\s*(.+)'
        match = re.search(route_pattern, line)
        
        if match:
            # Get everything after the path
            after_path = match.group(2)
            
            # Split by commas but be careful with nested parentheses
            parts = self.split_respecting_parentheses(after_path)
            
            # Filter out the actual route handler (function/arrow function)
            for part in parts:
                part = part.strip()
                # Skip if it's the route handler (contains => or function keyword)
                if '=>' in part or part.startswith('function') or part.startswith('(req') or part.startswith('async'):
                    break
                # Skip if it's just closing parentheses/braces
                if re.match(r'^[\)\}\s]*$', part):
                    continue
                # Extract middleware name (handle cases like 'middleware' or 'middleware()')
                middleware_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)', part)
                if middleware_match:
                    middleware_name = middleware_match.group(1)
                    middleware_names.append(middleware_name)
        
        return middleware_names
    
    def split_respecting_parentheses(self, text):
        """Split text by commas while respecting parentheses nesting"""
        parts = []
        current_part = ""
        paren_count = 0
        
        for char in text:
            if char == '(':
                paren_count += 1
            elif char == ')':
                paren_count -= 1
            elif char == ',' and paren_count == 0:
                parts.append(current_part.strip())
                current_part = ""
                continue
            current_part += char
        
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
        """Remove async/await keywords from function content"""
        # Remove async keyword from function declarations
        content = re.sub(r'\basync\s+', '', content)
        # Remove await keyword
        content = re.sub(r'\bawait\s+', '', content)
        # Remove optional chaining operators (?.)
        content = re.sub(r'\?\.', '.', content)
        return content
    
    def extract_function_body(self, lines, start_index, middleware):
        """Extract the function body from the route handler"""
        body_lines = []
        brace_count = 0
        in_function = False
        found_arrow = False
        
        for i in range(start_index, len(lines)):
            line = lines[i]
            
            # Look for arrow function or regular function
            if '=>' in line or 'function' in line:
                found_arrow = True
            
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
        
        return body_lines, i
    
    def create_function_signature(self, func_name, route_params, has_middleware=False):
        """Create function signature based on route info"""
        # No longer include 'next' in the main function signature
        params = ['method', 'req', 'res']
        
        # Add route parameters
        for param in route_params:
            params.append(param)
            
        return f"function {func_name}({', '.join(params)})"
    
    def create_aux_function_signature(self, func_name, route_params):
        """Create auxiliary function signature"""
        params = ['method', 'req', 'res']
        
        # Add route parameters
        for param in route_params:
            params.append(param)
            
        return f"function {func_name}_aux({', '.join(params)})"
    
    def group_routes_by_function(self, routes):
        """Group routes by function name and combine different HTTP methods"""
        grouped = {}
        
        for route in routes:
            func_name = route['func_name']
            path = route['path']
            key = f"{func_name}_{path}"  # Use path to distinguish similar function names
            
            if key not in grouped:
                grouped[key] = {
                    'func_name': func_name,
                    'path': path,
                    'route_params': route['route_params'],
                    'middleware': route.get('middleware', []),
                    'methods': {}
                }
            
            grouped[key]['methods'][route['method']] = route['body']
            
        return list(grouped.values())
    
    def convert_middleware_to_calls(self, middleware_names, aux_func_name, route_params):
        """Convert middleware names to function calls with req, res, and next middleware/aux function chained"""
        if not middleware_names:
            return []
        
        # Create the parameter list for the aux function call
        aux_params = ['method', 'req', 'res']
        aux_params.extend(route_params)
        aux_call = f"{aux_func_name}({', '.join(aux_params)})"
        
        # Build the chain from right to left (innermost to outermost)
        # Start with the aux function call as the innermost call
        current_call = aux_call
        
        # Chain middleware from last to first
        for middleware_name in reversed(middleware_names):
            current_call = f"{middleware_name}(req, res, {current_call})"
        
        return [f"{current_call};"]
    
    def generate_function_code(self, func_info):
        """Generate the complete function code"""
        func_name = func_info['func_name']
        route_params = func_info['route_params']
        methods = func_info['methods']
        middleware = func_info.get('middleware', [])
        
        # Create function signature (without next parameter)
        signature = self.create_function_signature(func_name, route_params, bool(middleware))
        
        # Generate function body
        lines = [f"{signature} {{"]
        
        # If there's middleware, call it with the aux function as next
        if middleware:
            aux_func_name = f"{func_name}_aux"
            middleware_calls = self.convert_middleware_to_calls(middleware, aux_func_name, route_params)
            for call in middleware_calls:
                lines.append(f"    {call}")
            lines.append("")
            
            # Generate auxiliary function
            aux_signature = self.create_aux_function_signature(func_name, route_params)
            lines.append(f"    {aux_signature} {{")
            
            # Add method checks in aux function
            method_keys = list(methods.keys())
            for i, method in enumerate(method_keys):
                body = methods[method]
                
                if i == 0:
                    lines.append(f"        if (method === \"{method}\") {{")
                else:
                    lines.append(f"        else if (method === \"{method}\") {{")
                
                # Process body lines
                for line in body:
                    if line.strip():
                        # Remove async/await
                        processed_line = self.remove_unsupported(line)
                        # Fix parameter references (req.params.id -> id)
                        for param in route_params:
                            processed_line = re.sub(f'req\\.params\\.{param}', param, processed_line)
                        lines.append(f"            {processed_line}")
                
                lines.append("        }")
            
            lines.append("    }")
        else:
            # No middleware, generate method checks directly
            method_keys = list(methods.keys())
            for i, method in enumerate(method_keys):
                body = methods[method]
                
                if i == 0:
                    lines.append(f"    if (method === \"{method}\") {{")
                else:
                    lines.append(f"    else if (method === \"{method}\") {{")
                
                # Process body lines
                for line in body:
                    if line.strip():
                        # Remove async/await
                        processed_line = self.remove_unsupported(line)
                        # Fix parameter references (req.params.id -> id)
                        for param in route_params:
                            processed_line = re.sub(f'req\\.params\\.{param}', param, processed_line)
                        lines.append(f"        {processed_line}")
                
                lines.append("    }")
        
        lines.append("}")
        lines.append("")
        
        return '\n'.join(lines)
    
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
        i = 0
        
        while i < len(lines):
            line = lines[i]
            # Updated to receive middleware as well
            method, path, middleware = self.extract_route_info(line)
            
            if method and path:
                func_name = self.path_to_function_name(path)
                route_params = self.extract_route_params(path)
                
                # Extract function body
                body_lines, end_index = self.extract_function_body(lines, i, middleware)
                
                routes.append({
                    'method': method,
                    'path': path,
                    'func_name': func_name,
                    'route_params': route_params,
                    'middleware': middleware,
                    'body': body_lines
                })
                
                i = end_index + 1
            else:
                i += 1
        
        # Don't group routes - keep them separate
        output_lines = []
        
        # Add header comments and imports (copy from original file until first route)
        header_lines = []
        for line in lines:
            if re.search(r'app\.(get|post|put|delete|patch)', line):
                break
            header_lines.append(line)
        
        output_lines.extend(header_lines)
        
        # Generate function code for each route separately
        processed_functions = set()
        
        for route in routes:
            func_key = f"{route['func_name']}_{route['path']}"
            if func_key not in processed_functions:
                # Find all methods for this function
                same_func_routes = [r for r in routes if r['func_name'] == route['func_name'] and r['path'] == route['path']]
                
                func_info = {
                    'func_name': route['func_name'],
                    'route_params': route['route_params'],
                    'middleware': route['middleware'],
                    'methods': {}
                }
                
                for same_route in same_func_routes:
                    func_info['methods'][same_route['method']] = same_route['body']
                
                function_code = self.generate_function_code(func_info)
                output_lines.append(function_code)
                processed_functions.add(func_key)
        
        # Add utility functions (copy from original file)
        if routes:
            utility_started = False
            for line in lines:
                if line.strip().startswith('function'):
                    utility_started = True
                if utility_started:
                    updated_line = self.remove_unsupported(line)
                    output_lines.append(updated_line)
        
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

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 express_transformer.py <input_file> <output_file>")
        print("Example: python3 express_transformer.py server.js index.js")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    transformer = ExpressRouteTransformer()
    success = transformer.transform_file(input_file, output_file)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()