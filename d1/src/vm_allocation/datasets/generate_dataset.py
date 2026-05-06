import random
from models.server import Server
from models.vm import VM

def random_power_of_two(min_exp=1, max_exp=6):
    return 2 ** random.randint(min_exp, max_exp)


def random_even(min_val, max_val):
    val = random.randint(min_val, max_val)
    return val if val % 2 == 0 else val + 1


def generate_servers(n):
    return [
        Server(
            i,
            cpu=random_power_of_two(5, 7),   # 32 à 128
            ram=random_even(64, 256),
            storage=random.randint(500, 2000),
            bw=random.randint(100, 1000),
        )
        for i in range(n)
    ]


def generate_vms(n):
    vms = []
    for i in range(n):

        if random.random() < 0.8:
            cpu = random_power_of_two(1, 3)  # 2,4,8
        else:
            cpu = random_power_of_two(3, 4)  # 8,16

        vms.append(
            VM(
                i,
                cpu=cpu,
                ram=random_even(2, 32),
                storage=random.randint(10, 200),
                bw=random.randint(1, 100),
            )
        )
    return vms