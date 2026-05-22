import math

def round_to_next_5or0(n):
    if n % 5 == 0:
        return n
    else:
        return n - (n % 5) + 5
    
def circle_dia(area):
    return round_to_next_5or0(math.sqrt(area * 4 / math.pi),2)

