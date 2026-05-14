from typing import List
import random

from matplotlib.pylab import rand
from vm_allocation.models import Server, VM, Context


def random_power_of_two(min_exp: int = 1, max_exp: int = 6):
    return 2 ** random.randint(min_exp, max_exp)


def random_even(min_val: int, max_val: int):
    min_val = min_val if min_val % 2 == 0 else min_val + 1
    max_val = max_val if max_val % 2 == 0 else max_val - 1
    if min_val > max_val:
        raise ValueError(
            "Invalid boundaries, min value should be inferior or equal to max."
        )
    val = random.randint(0, (max_val - min_val) // 2)
    return min_val + val * 2


def generate_n_servers(n: int) -> List[Server[int]]:
    return [
        Server(
            i,
            cpu=random_power_of_two(5, 7),  # 32 à 128
            ram=random_even(64, 256),
            storage=random.randint(500, 2000),
            bw=random.randint(200, 2000),
        )
        for i in range(n)
    ]


def generate_n_vms_with_context(
    n: int,
    context: Context[int],
    affinity_chance: float = 0.1,
    anti_affinity_server_selection_chance: float = 0.1,
    anti_affinity_chance: float = 0.1,
    verbose: bool = False,
) -> tuple[list[VM[int]], Context[int]]:
    if verbose:
        print(f"Creating {n} VMs")
    servers = [server.copy() for server in context.get_servers()]
    nb_server = len(servers)
    if verbose:
        print(f"Server number : {nb_server}")
    all_vms = []

    for i in range(n):
        if verbose:
            print(f"Creating VM {i}")
        vm = generate_vm(i)

        accepting_server_idx = [
            i for i, server in enumerate(servers) if server.can_host(vm)
        ]

        if len(accepting_server_idx) == 0:
            if verbose:
                print("Could not insert it")
            # No place left
            break

        chosen_server_id = random.choice(accepting_server_idx)

        if verbose:
            print(f"Chosen server id : {chosen_server_id}")

        servers[chosen_server_id].add_vm(vm)

        # For all neighbors, affinity_chance to develop an affinity
        server = servers[chosen_server_id]
        list_vm = server.get_vms()

        for friend in list_vm:
            if friend.id != vm.id:
                if random.random() < affinity_chance:
                    print("Affinity added with vm :", friend.id)
                    vm.add_affinity(friend)

        for j in range(nb_server):
            if (
                j != chosen_server_id
                and random.random() < anti_affinity_server_selection_chance
            ):
                for not_friend in servers[j].get_vms():
                    if random.random() < anti_affinity_chance:
                        print("antiffinity added with vm :", not_friend.id)
                        vm.add_anti_affinity(not_friend)
                        not_friend.add_anti_affinity(vm)

        all_vms.append(vm)

    random.shuffle(all_vms)

    return all_vms, Context(servers)


def generate_vm[ID_T](i: ID_T) -> VM[ID_T]:

    if random.random() < 0.8:
        cpu = random_power_of_two(1, 3)  # 2,4,8
    else:
        cpu = random_power_of_two(3, 4)  # 8,16

    res = VM(
        i,
        cpu=cpu,
        ram=random_even(2, 32),
        storage=random.randint(10, 200),
        bw=random.randint(1, 100),
    )
    return res
