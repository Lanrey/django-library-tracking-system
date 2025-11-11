import random
rand_list = random.choices(range(1,21), k=10)

list_comprehension_below_10 = rand_list = [num for num in rand_list if num < 10]

#using filter function

list_comprehension_below_10 = rand_list = list(filter(lambda x: x < 10, rand_list))