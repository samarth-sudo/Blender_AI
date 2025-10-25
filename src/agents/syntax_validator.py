"""
Syntax Validator Agent - Fourth agent in the pipeline.

Responsibility: Validate generated Blender code before execution.

This agent performs:
1. Python syntax validation (AST parsing)
2. Security checks (dangerous operations)
3. Blender API usage validation
4. Code quality checks

Catching errors here prevents failed Blender executions and saves time.
"""

import ast
import re
from typing import List, Tuple

from src.agents.base_agent import BaseAgent
from src.models.schemas import BlenderCode, ValidationResult
from src.utils.errors import SyntaxError as SyntaxValidationError


class SyntaxValidatorAgent(BaseAgent):
    """
    Syntax Validator Agent: Validate Python code before execution.

    This agent acts as a gatekeeper to prevent bad code from reaching Blender.

    Checks performed:
    - Python syntax (AST parsing)
    - Security (no dangerous operations)
    - Required imports (bpy)
    - Common Blender API mistakes
    - Code structure

    Example:
        validator = SyntaxValidatorAgent()
        result = validator.run(generated_code)
        if not result.is_valid:
            print(result.errors)
    """

    # Forbidden operations for security
    FORBIDDEN_OPERATIONS = [
        "os.system",
        "subprocess",
        "eval(",
        "exec(",
        "__import__",
        "open(",  # File operations outside Blender context
        "compile(",
        "globals()",
        "locals()",
    ]

    # Required imports for Blender scripts
    REQUIRED_IMPORTS = ["bpy"]

    def __init__(self):
        """Initialize Syntax Validator Agent."""
        super().__init__("SyntaxValidatorAgent")

    def execute(self, code: BlenderCode) -> ValidationResult:
        """
        Validate Blender Python code.

        Args:
            code: BlenderCode object to validate

        Returns:
            ValidationResult with errors/warnings
        """
        self.logger.info(f"Validating code ({len(code.code)} characters)")

        errors = []
        warnings = []

        # Check 1: Python syntax
        syntax_valid, syntax_errors = self._check_syntax(code.code)
        if not syntax_valid:
            errors.extend(syntax_errors)

        # Check 2: Security
        security_valid, security_errors = self._check_security(code.code)
        if not security_valid:
            errors.extend(security_errors)

        # Check 3: Required imports
        imports_valid, import_errors = self._check_imports(code.code)
        if not imports_valid:
            errors.extend(import_errors)

        # Check 4: Blender API usage (warnings only)
        api_warnings = self._check_blender_api(code.code)
        warnings.extend(api_warnings)

        # Check 5: Code structure
        structure_warnings = self._check_structure(code.code)
        warnings.extend(structure_warnings)

        # Calculate score
        is_valid = len(errors) == 0
        score = 1.0 if is_valid else (0.5 if len(errors) <= 2 else 0.0)

        self.logger.info(
            f"Validation complete: {'PASS' if is_valid else 'FAIL'}",
            errors=len(errors),
            warnings=len(warnings)
        )

        return ValidationResult(
            is_valid=is_valid,
            score=score,
            errors=errors,
            warnings=warnings,
            metadata={
                "code_length": len(code.code),
                "line_count": len(code.code.split('\n'))
            }
        )

    def _check_syntax(self, code: str) -> Tuple[bool, List[str]]:
        """
        Check Python syntax using AST parser.

        Args:
            code: Python code string

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        try:
            ast.parse(code)
            return True, []
        except SyntaxError as e:
            error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
            if e.text:
                error_msg += f"\n  {e.text.strip()}"
            return False, [error_msg]
        except Exception as e:
            return False, [f"Failed to parse code: {str(e)}"]

    def _check_security(self, code: str) -> Tuple[bool, List[str]]:
        """
        Check for dangerous operations.

        Args:
            code: Python code string

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        for forbidden in self.FORBIDDEN_OPERATIONS:
            if forbidden in code:
                # Check if it's in a comment
                lines_with_forbidden = [
                    line for line in code.split('\n')
                    if forbidden in line and not line.strip().startswith('#')
                ]

                if lines_with_forbidden:
                    errors.append(
                        f"Security: Forbidden operation '{forbidden}' found. "
                        f"Blender scripts should not use this for safety."
                    )

        is_valid = len(errors) == 0
        return is_valid, errors

    def _check_imports(self, code: str) -> Tuple[bool, List[str]]:
        """
        Check for required imports.

        Args:
            code: Python code string

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        for required_import in self.REQUIRED_IMPORTS:
            # Check for "import bpy" or "from bpy import ..."
            import_patterns = [
                f"import {required_import}",
                f"from {required_import} import",
            ]

            has_import = any(pattern in code for pattern in import_patterns)

            if not has_import:
                errors.append(f"Missing required import: '{required_import}'")

        is_valid = len(errors) == 0
        return is_valid, errors

    def _check_blender_api(self, code: str) -> List[str]:
        """
        Check for common Blender API mistakes (warnings only).

        Args:
            code: Python code string

        Returns:
            List of warnings
        """
        warnings = []

        # Common mistake: Not checking if context is valid
        if "bpy.context.active_object" in code and "if bpy.context.active_object" not in code:
            warnings.append(
                "Consider checking if bpy.context.active_object exists before using it"
            )

        # Common mistake: Not setting context correctly for operators
        if "bpy.ops." in code and "bpy.context.view_layer.objects.active" not in code:
            # Check if there are any operator calls that might need context
            operator_count = len(re.findall(r'bpy\.ops\.\w+\.\w+', code))
            if operator_count > 3:
                warnings.append(
                    "Multiple bpy.ops calls detected. Ensure correct context is set."
                )

        # Check for deprecated API usage
        deprecated_patterns = {
            "bpy.context.scene.objects.link": "Use bpy.context.collection.objects.link instead",
            "bpy.context.scene.objects.unlink": "Use bpy.context.collection.objects.unlink instead",
        }

        for deprecated, suggestion in deprecated_patterns.items():
            if deprecated in code:
                warnings.append(f"Deprecated API: '{deprecated}'. {suggestion}")

        # Check for potential performance issues
        if code.count("bpy.ops.") > 20:
            warnings.append(
                "High number of operator calls (bpy.ops). "
                "Consider using direct data manipulation for better performance."
            )

        return warnings

    def _check_structure(self, code: str) -> List[str]:
        """
        Check code structure and organization.

        Args:
            code: Python code string

        Returns:
            List of warnings
        """
        warnings = []

        lines = code.split('\n')

        # Check if code is too short (probably incomplete)
        if len(lines) < 20:
            warnings.append("Code seems very short. Ensure all required steps are included.")

        # Check for main execution
        if 'if __name__ == "__main__"' not in code:
            warnings.append(
                "No main execution block found. Code should have 'if __name__ == \"__main__\"'"
            )

        # Check for save operation
        if "save" not in code.lower() and "blend" in code.lower():
            warnings.append("No save operation detected. Ensure .blend file is saved.")

        # Check for simulation baking
        if "bake" not in code.lower() and ("rigid" in code.lower() or "fluid" in code.lower() or "cloth" in code.lower()):
            warnings.append(
                "No baking operation detected. Physics simulations must be baked."
            )

        return warnings

    def validate_and_fix(self, code: BlenderCode) -> Tuple[BlenderCode, ValidationResult]:
        """
        Validate code and attempt automatic fixes for common issues.

        Args:
            code: BlenderCode to validate and fix

        Returns:
            Tuple of (fixed_code, validation_result)
        """
        result = self.execute(code)

        if result.is_valid:
            return code, result

        # Attempt to fix common issues
        fixed_code_str = code.code

        # Fix 1: Add missing bpy import
        if "Missing required import: 'bpy'" in result.errors:
            fixed_code_str = "import bpy\n" + fixed_code_str
            self.logger.info("Auto-fixed: Added 'import bpy'")

        # Fix 2: Add math import if math functions are used
        if ("math." in fixed_code_str or "radians" in fixed_code_str) and "import math" not in fixed_code_str:
            # Insert after bpy import
            lines = fixed_code_str.split('\n')
            for i, line in enumerate(lines):
                if "import bpy" in line:
                    lines.insert(i + 1, "import math")
                    break
            fixed_code_str = '\n'.join(lines)
            self.logger.info("Auto-fixed: Added 'import math'")

        # Create new BlenderCode with fixes
        fixed_code = BlenderCode(
            code=fixed_code_str,
            template_used=code.template_used,
            complexity_score=code.complexity_score,
            estimated_execution_time=code.estimated_execution_time
        )

        # Re-validate
        new_result = self.execute(fixed_code)

        return fixed_code, new_result

    def get_code_statistics(self, code: str) -> dict:
        """
        Get detailed statistics about the code.

        Args:
            code: Python code string

        Returns:
            Dictionary with statistics
        """
        lines = code.split('\n')

        # Count different types of lines
        blank_lines = sum(1 for line in lines if not line.strip())
        comment_lines = sum(1 for line in lines if line.strip().startswith('#'))
        code_lines = len(lines) - blank_lines - comment_lines

        # Count bpy operations
        bpy_ops_count = len(re.findall(r'bpy\.ops\.\w+\.\w+', code))
        bpy_data_count = len(re.findall(r'bpy\.data\.\w+', code))
        bpy_context_count = len(re.findall(r'bpy\.context\.\w+', code))

        # Count functions and classes
        try:
            tree = ast.parse(code)
            function_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
            class_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
        except:
            function_count = 0
            class_count = 0

        return {
            "total_lines": len(lines),
            "code_lines": code_lines,
            "comment_lines": comment_lines,
            "blank_lines": blank_lines,
            "functions": function_count,
            "classes": class_count,
            "bpy_operators": bpy_ops_count,
            "bpy_data_access": bpy_data_count,
            "bpy_context_access": bpy_context_count,
            "characters": len(code),
        }
