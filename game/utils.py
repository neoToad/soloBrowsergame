import random

def roll_d20():
    return random.randint(1, 20)

def stat_modifier(stat_value):
    return (stat_value - 10) // 2
