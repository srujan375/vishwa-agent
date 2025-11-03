#!/usr/bin/env python3
"""
Script to print the Fibonacci sequence till 10000
"""

def fibonacci_till_1000():
    """Generate and print Fibonacci numbers up to 1000"""
    a, b = 0, 1
    
    print("Fibonacci sequence till 1000:")
    print(a)
    
    while b <= 1000:
        print(b)
        a, b = b, a + b

if __name__ == "__main__":
    fibonacci_till_10000()
