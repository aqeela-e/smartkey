import time
from typing import List, Optional, Tuple

from .base import AIKeyGenerator, randomness_penalty
from .entropy_source import EntropySource, get_entropy_source

_TOURNAMENT_SIZE = 3
_BIT_FLIP_PROB = 0.05

class GeneticAlgorithmGenerator(AIKeyGenerator):

    @staticmethod
    def evaluate_randomness(individual, tolerance_sigma: float = 2.0):
        return (-randomness_penalty(individual, tolerance_sigma=tolerance_sigma),)

    @staticmethod
    def _tournament(fitness: List[float], source: EntropySource) -> List[int]:
        n = len(fitness)
        u = source.uniform(n * _TOURNAMENT_SIZE)
        picks = []
        for k in range(n):
            best = None
            for j in range(_TOURNAMENT_SIZE):
                idx = min(int(u[k * _TOURNAMENT_SIZE + j] * n), n - 1)
                if best is None or fitness[idx] > fitness[best]:
                    best = idx
            picks.append(best)
        return picks

    @staticmethod
    def _two_point_crossover(a: List[int], b: List[int], source: EntropySource) -> None:
        size = min(len(a), len(b))
        if size < 2:
            return
        p1 = source.randint(1, size)
        p2 = source.randint(1, size - 1)
        if p2 >= p1:
            p2 += 1
        else:
            p1, p2 = p2, p1
        a[p1:p2], b[p1:p2] = b[p1:p2], a[p1:p2]

    @staticmethod
    def _flip_bit_mutation(ind: List[int], source: EntropySource) -> None:
        u = source.uniform(len(ind))
        for i in range(len(ind)):
            if u[i] < _BIT_FLIP_PROB:
                ind[i] = 1 - ind[i]

    def generate(
        self,
        bit_length: int,
        population_size: int = 50,
        generations: int = 100,
        crossover_rate: float = 0.7,
        mutation_rate: float = 0.2,
        tolerance_sigma: float = 2.0,
        random_state: Optional[int] = None,
        **kwargs
    ) -> Tuple[bytes, dict]:

        if bit_length < 1 or population_size < 1:
            raise ValueError("bit_length dan population_size harus >= 1")

        start_time = time.perf_counter()
        source = get_entropy_source(random_state)
        tol = float(tolerance_sigma)

        def fitness_of(ind):
            return -randomness_penalty(ind, tolerance_sigma=tol)

        flat = source.bits(population_size * bit_length)
        pop = [
            flat[i * bit_length:(i + 1) * bit_length].astype(int).tolist()
            for i in range(population_size)
        ]
        fit = [fitness_of(ind) for ind in pop]
        evaluations = population_size
        history = [-max(fit)]

        for _ in range(generations):

            picks = self._tournament(fit, source)
            offspring = [pop[i][:] for i in picks]
            off_fit = [fit[i] for i in picks]
            valid = [True] * population_size

            u_cx = source.uniform(population_size // 2 + 1)
            for k, i in enumerate(range(1, population_size, 2)):
                if u_cx[k] < crossover_rate:
                    self._two_point_crossover(offspring[i - 1], offspring[i], source)
                    valid[i - 1] = valid[i] = False

            u_mut = source.uniform(population_size)
            for i in range(population_size):
                if u_mut[i] < mutation_rate:
                    self._flip_bit_mutation(offspring[i], source)
                    valid[i] = False

            for i in range(population_size):
                if not valid[i]:
                    off_fit[i] = fitness_of(offspring[i])
                    evaluations += 1

            pop, fit = offspring, off_fit
            history.append(-max(fit))

        best_fit = max(fit)
        best_idx = [i for i, f in enumerate(fit) if f == best_fit]
        best_ind = pop[best_idx[source.randbelow(len(best_idx))]]

        bit_string = "".join(str(bit) for bit in best_ind)
        seed_bytes = self.bit_string_to_bytes(bit_string)

        end_time = time.perf_counter()

        metrics = {
            "algorithm": "Genetic Algorithm (GA)",
            "time_ms": (end_time - start_time) * 1000,
            "generations": generations,
            "population_size": population_size,
            "tolerance_sigma": tolerance_sigma,
            "evaluations": evaluations,

            "best_fitness": best_fit,
            "best_penalty": -best_fit,
            "converged": bool(best_fit == 0),
            "convergence_penalty": history,
            "entropy_source": source.name,
            "entropy_source_secure": source.secure,
        }

        return seed_bytes, metrics