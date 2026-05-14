import random

from matplotlib.pylab import rand
from vm_allocation.models import Server, VM, Context

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
            bw=random.randint(200, 2000),
        )
        for i in range(n)
    ]


def generate_vms_with_context(n, context: Context):
    print(f"lets create {n} vm")
    servers = [server.copy() for server in context.get_servers()]
    nb_serveur = len(servers)
    print("nb serveur: ", nb_serveur)
    all_vms = []
    for i in range(n):
        print("create vm :",i)
        # creer la VM
        vm = generate_vms(i)

        # je choisi un serveur au hasard
        serv_choosen = random.randint(0, nb_serveur - 1)
        print("server choosen : ", serv_choosen)
        start = serv_choosen

        # je verifie que le serveur n'est pas plein
        while not servers[serv_choosen].can_host(vm) :

            serv_choosen = (serv_choosen + 1) % nb_serveur 
            if serv_choosen == start:
                raise Exception("No server can host this VM")

        print("serveur choosen:",serv_choosen)
        #jajoute la VM
        servers[serv_choosen].add_vm(vm)

        #pour tout les voisins de la vm 25% detre avec affinités
        server = servers[serv_choosen]
        list_vm = server.get_vms()

        for friend in list_vm:
            if friend.id != vm.id:
                if random.random() < 0.25:
                    print("affinity added with vm :",friend.id)
                    vm.add_affinity(friend)
                    friend.add_affinity(vm)

        for j in range(nb_serveur):
            if j != serv_choosen:
                for not_friend in servers[j].get_vms():
                    if random.random() < 0.20:
                        print("antiffinity added with vm :",not_friend.id)
                        vm.add_anti_affinity(not_friend)
                        not_friend.add_anti_affinity(vm)

        all_vms.append(vm)
        random.shuffle(all_vms)

        empty_context = context

    return all_vms, Context(servers)


        




def generate_vms(i):

    if random.random() < 0.8:
        cpu = random_power_of_two(1, 3)  # 2,4,8
    else:
        cpu = random_power_of_two(3, 4)  # 8,16

    res = VM(i,cpu=cpu,ram=random_even(2, 32),storage=random.randint(10, 200),bw=random.randint(1, 100))
    return res