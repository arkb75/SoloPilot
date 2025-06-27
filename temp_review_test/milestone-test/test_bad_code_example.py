#!/usr/bin/env python3
"""
Test file with intentionally bad code for CI validation.
This file contains various code quality issues to test the AI reviewer.
"""

import requests  # Unused import

# Global variable (bad practice)
GLOBAL_CONFIG = {"key": "value"}


class BadCodeExample:
    """Example class with various code issues."""

    def __init__(self):
        # Hard-coded values
        self.api_key = "sk-1234567890abcdef"  # Security issue: exposed API key
        self.password = "admin123"  # Security issue: hardcoded password
        self.data = []

    def process_data(self, items):  # Missing type hints
        """Process data with poor error handling."""
        result = []
        for i in range(len(items)):  # Not pythonic
            try:
                # Broad exception catching
                result.append(items[i] * 2)
            except:  # Bare except clause
                pass  # Silently ignoring errors

        return result

    def unsafe_sql_query(self, user_input):
        """Execute SQL with injection vulnerability."""
        # SQL injection vulnerability
        query = f"SELECT * FROM users WHERE name = '{user_input}'"
        # Would execute query here
        return query

    def complex_function(self, a, b, c, d, e, f, g):  # Too many parameters
        """Function with high complexity."""
        if a:
            if b:
                if c:
                    if d:  # Deep nesting
                        if e:
                            if f:
                                if g:
                                    return True
        return False

    def unused_method(self):  # Dead code
        """This method is never called."""
        return "unused"

    def eval_user_input(self, user_code):
        """Dangerous use of eval."""
        # Security issue: using eval on user input
        result = eval(user_code)
        return result

    def memory_leak_example(self):
        """Function that could cause memory issues."""
        # Creating large list in memory
        huge_list = [i for i in range(10000000)]
        # Not releasing reference
        self.data.extend(huge_list)

    def sync_blocking_call(self):
        """Blocking I/O without timeout."""
        # No timeout specified
        response = requests.get("https://api.example.com/data")
        return response.json()


def another_bad_function(x, y):
    """Function with missing return type hint."""
    # Magic numbers
    if x > 42:
        return y * 2.5
    elif x < 10:
        return y / 3.14  # Could cause ZeroDivisionError
    else:
        print(f"Debug: x={x}, y={y}")  # Debug print left in code


# Code duplication
def calculate_area_circle(radius):
    """Calculate circle area."""
    return 3.14159 * radius * radius


def calculate_area_circle_duplicate(r):
    """Duplicate function."""
    return 3.14159 * r * r


if __name__ == "__main__":
    # Running code at module level
    example = BadCodeExample()
    print(example.process_data([1, 2, "three", 4]))  # Type mismatch

    # Dangerous operations
    user_input = input("Enter SQL: ")
    print(example.unsafe_sql_query(user_input))
