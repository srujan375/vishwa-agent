"""
Script to print asterisks in a pyramid sequence
"""

def print_pyramid(rows):
    """
    Print a pyramid of asterisks

    Args:
        rows (int): Number of rows in the pyramid
    """
    for i in range(1, rows + 1):
        # Print leading spaces for alignment
        spaces = " " * (rows - i)
        # Print asterisks
        stars = "*" * (2 * i - 1)
        print(spaces + stars)


def print_pyramid_simple(rows):
    """
    Print a simple left-aligned pyramid of asterisks

    Args:
        rows (int): Number of rows in the pyramid
    """
    for i in range(1, rows + 1):
        print("*" * i)


def print_pyramid_inverted(rows):
    """
    Print an inverted pyramid of asterisks

    Args:
        rows (int): Number of rows in the pyramid
    """
    for i in range(rows, 0, -1):
        # Print leading spaces for alignment
        spaces = " " * (rows - i)
        # Print asterisks
        stars = "*" * (2 * i - 1)
        print(spaces + stars)


def print_diamond(rows):
    """
    Print a diamond pattern of asterisks

    Args:
        rows (int): Number of rows in the upper half of the diamond
    """
    # Upper pyramid
    for i in range(1, rows + 1):
        spaces = " " * (rows - i)
        stars = "*" * (2 * i - 1)
        print(spaces + stars)
    # Lower inverted pyramid
    for i in range(rows - 1, 0, -1):
        spaces = " " * (rows - i)
        stars = "*" * (2 * i - 1)
        print(spaces + stars)


def print_hollow_pyramid(rows):
    """
    Print a hollow pyramid of asterisks

    Args:
        rows (int): Number of rows in the pyramid
    """
    for i in range(1, rows + 1):
        if i == rows:
            # Print the base of the pyramid
            print("*" * (2 * i - 1))
        else:
            # Print hollow pyramid
            spaces = " " * (rows - i)
            if i == 1:
                stars = "*"
            else:
                stars = "*" + " " * (2 * i - 3) + "*"
            print(spaces + stars)


if __name__ == "__main__":
    print("=== Centered Pyramid ===")
    print_pyramid(5)

    print("\n=== Simple Left-Aligned Pyramid ===")
    print_pyramid_simple(5)

    print("\n=== Inverted Pyramid ===")
    print_pyramid_inverted(5)

    print("\n=== Diamond Pattern ===")
    print_diamond(5)

    print("\n=== Hollow Pyramid ===")
    print_hollow_pyramid(5)

    print("\n=== Custom Pyramid (10 rows) ===")
    print_pyramid(10)
