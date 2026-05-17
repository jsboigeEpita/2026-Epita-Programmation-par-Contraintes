"""Provides utility functions for random number generation."""

import random
from vm_allocation.models import Context

__all__ = ["random_power_of_two", "random_even", "fragmentation_percentage"]


def random_power_of_two(min_exp: int = 1, max_exp: int = 6) -> int:
    """Generates a random power of two.

    The exponent is chosen uniformly between `min_exp`
    and `max_exp` (inclusive), and the returned value
    is computed as:

        2 ** exponent

    Parameters
    ----------
    min_exp : int, optional
        Minimum exponent value, by default 1
    max_exp : int, optional
        Maximum exponent value, by default 6

    Returns
    -------
    int
        A random power of two.
    """
    return 2 ** random.randint(min_exp, max_exp)


def random_even(min_val: int, max_val: int) -> int:
    """Generate a random even integer within a given range.

    The function adjusts the boundaries if needed so that
    both become even numbers before generating the value.

    Parameters
    ----------
    min_val : int
        Minimum allowed value.
    max_val : int
        Maximum allowed value.

    Returns
    -------
    int
        A random even integer between `min_val` and `max_val`.

    Raises
    ------
    ValueError
        If no valid even number exists in the range.
    """
    min_val = min_val if min_val % 2 == 0 else min_val + 1
    max_val = max_val if max_val % 2 == 0 else max_val - 1
    if min_val > max_val:
        raise ValueError(
            "Invalid boundaries, min value should be inferior or equal to max."
        )
    val = random.randint(0, (max_val - min_val) // 2)
    return min_val + val * 2

def fragmentation_percentage(self) -> float:
    """Compute datacenter fragmentation and server usage percentages.

        The fragmentation score measures how imbalanced the remaining
        resources are across all servers. A server is considered highly
        fragmented when one resource becomes saturated while others remain
        largely available.

        Fragmentation is computed independently for each server using the
        ratio between the minimum and maximum remaining resource capacities
        (CPU, RAM, storage, bandwidth), then averaged across the datacenter.

        The method also computes the percentage of servers currently hosting
        at least one VM.

        Returns
        -------
        tuple[float, float]
            A tuple containing:

            - fragmentation percentage (0 to 100)
            - used server percentage (0 to 100)
    """

    if not self.servers:
        return 0.0, 0.0

    fragmentations = []

    for server in self.servers.values():
        # Remaining CPU percentage
        remaining_cpu = (server.cpu_capacity - server.cpu_usage) / server.cpu_capacity

        # Remaining RAM percentage
        remaining_ram = (server.ram_capacity - server.ram_usage) / server.ram_capacity

        # Remaining storage percentage
        remaining_storage = (server.storage_capacity - server.storage_usage) / server.storage_capacity

        # Remaining bandwidth percentage
        remaining_bw = (server.bw_capacity - server.bw_usage) / server.bw_capacity

        # Group all remaining resource ratios together
        free_ratios = [remaining_cpu,remaining_ram, remaining_storage, remaining_bw]

        max_ratio = max(free_ratios)
        min_ratio = min(free_ratios)

        # serveur plein
        if max_ratio == 0:
            fragmentation = 0

        else:
            fragmentation = 1 - (min_ratio / max_ratio)

        fragmentations.append(fragmentation)

        res_fragmentation = sum(fragmentations) / len(fragmentations) * 100


        total_servers = len(self.servers)

        if total_servers == 0:
            return 0.0

        used_servers = sum(1 for s in self.servers.values() if s.vms)

        server_used = used_servers / total_servers * 100

    return res_fragmentation, server_used
        
