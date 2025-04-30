from collections import defaultdict
import re

def parse_timeloop_stats(content):
    
    results = {
        'energy_per_compute_fJ': {},      # fJ/Compute per component
        'total_energy_uJ': None,          # Total energy
        'memory_energy_pJ': {},           # Total memory energy in pJ
        'memory_traffic': {},             # Scalar accesses per memory level
        'utilization_percent': {},        # Utilization per component and overall
        'computes_per_cycle': None,       # Throughput
        'actual_computes': None,          # Needed for later calc
        'cycles': None                    # Needed for later calc
    }

    # 1. Energy per compute (fJ/Compute)
    energy_compute_matches = re.findall(r"fJ/Compute\s+((?:.|\n)+?)\n\n", content)
    if energy_compute_matches:
        for line in energy_compute_matches[0].split('\n'):
            match = re.match(r"\s*(\S+)\s*=\s*([\d.]+)", line)
            if match:
                component, value = match.groups()
                results['energy_per_compute_fJ'][component] = float(value)

    # 2. Total energy (Summary Stats)
    total_energy_match = re.search(r"Energy:\s+([\d.]+)\s*uJ", content)
    if total_energy_match:
        results['total_energy_uJ'] = float(total_energy_match.group(1))

    # 3. Actual Computes and Cycles
    actual_compute_match = re.search(r"Actual Computes\s*=\s*(\d+)", content)
    if actual_compute_match:
        results['actual_computes'] = int(actual_compute_match.group(1))

    cycle_match = re.search(r"Cycles:\s*(\d+)", content)
    if cycle_match:
        results['cycles'] = int(cycle_match.group(1))

    if results['actual_computes'] and results['cycles']:
        results['computes_per_cycle'] = results['actual_computes'] / results['cycles']

    # 4. Memory traffic (scalar accesses per level)
    memory_traffic_matches = re.findall(r"=== (\w+) ===\n\s*Total scalar accesses\s*:\s*(\d+)", content)
    for level, accesses in memory_traffic_matches:
        results['memory_traffic'][level] = int(accesses)

    # 5. Memory energy: per component from `Energy (total)` lines
    energy_total_matches = re.findall(r"=== (\w+) ===.+?Energy \(total\)\s*:\s*([\d.]+)\s*pJ", content, re.DOTALL)
    for level, energy in energy_total_matches:
        results['memory_energy_pJ'][level] = float(energy)

    # 6. Utilization (MAC unit + overall)
    mac_util_match = re.search(r"MAC.+?Utilized instances \(average\)\s*:\s*([\d.]+)", content, re.DOTALL)
    if mac_util_match:
        results['utilization_percent']['MAC'] = float(mac_util_match.group(1))

    overall_util_match = re.search(r"Utilization:\s*([\d.]+)%", content)
    if overall_util_match:
        results['utilization_percent']['overall'] = float(overall_util_match.group(1))

    return results


def aggregate_timeloop_runs(parsed_runs):
    
    aggregate = {
        'total_energy_uJ': 0.0,
        'memory_energy_pJ': defaultdict(float),
        'memory_traffic': defaultdict(int),
        'energy_per_compute_fJ': {},
        'utilization_percent': {},
        'computes_per_cycle': 0.0,
    }

    total_computes = 0
    total_cycles = 0
    fj_weighted_sums = defaultdict(float)
    fj_total_computes = defaultdict(float)
    utilization_weighted = defaultdict(float)
    utilization_weights = defaultdict(float)

    for run in parsed_runs:
        # Sum total energy
        aggregate['total_energy_uJ'] += run['total_energy_uJ']

        # Sum memory energy
        for level, energy in run['memory_energy_pJ'].items():
            aggregate['memory_energy_pJ'][level] += energy

        # Sum memory traffic
        for level, accesses in run['memory_traffic'].items():
            aggregate['memory_traffic'][level] += accesses

        # fJ/Compute (weighted by actual computes)
        computes = run['actual_computes']
        for comp, fj in run['energy_per_compute_fJ'].items():
            fj_weighted_sums[comp] += fj * computes
            fj_total_computes[comp] += computes

        # Utilization (weighted by cycles)
        if run['cycles']:
            for key, util in run['utilization_percent'].items():
                utilization_weighted[key] += util * run['cycles']
                utilization_weights[key] += run['cycles']

        # Total actual computes and cycles for throughput
        total_computes += computes
        total_cycles += run['cycles']

    # Finalize fJ/Compute
    for comp in fj_weighted_sums:
        aggregate['energy_per_compute_fJ'][comp] = fj_weighted_sums[comp] / fj_total_computes[comp]

    # Finalize utilization
    for key in utilization_weighted:
        aggregate['utilization_percent'][key] = utilization_weighted[key] / utilization_weights[key]

    # Finalize computes per cycle
    if total_cycles > 0:
        aggregate['computes_per_cycle'] = total_computes / total_cycles

    # Attach raw totals (in case needed later)
    aggregate['total_actual_computes'] = total_computes
    aggregate['total_cycles'] = total_cycles

    return aggregate