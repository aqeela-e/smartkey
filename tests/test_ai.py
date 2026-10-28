import pytest
from modules.ai.genetic_algorithm import GeneticAlgorithmGenerator
from modules.ai.neural_network import NeuralNetworkGenerator
from modules.ai.ant_colony import AntColonyOptimizationGenerator

def test_genetic_algorithm():
    gen = GeneticAlgorithmGenerator()
    seed, metrics = gen.generate(bit_length=128, population_size=10, generations=5)
    
    assert isinstance(seed, bytes)
    assert len(seed) == 16 # 128 bits
    assert "time_ms" in metrics
    assert metrics["algorithm"] == "Genetic Algorithm (GA)"

def test_neural_network():
    gen = NeuralNetworkGenerator()
    seed, metrics = gen.generate(bit_length=128, hidden_layers=(10,), noise_std_dev=1.0)
    
    assert isinstance(seed, bytes)
    assert len(seed) == 16
    assert "time_ms" in metrics
    assert metrics["algorithm"] == "Artificial Neural Network (ANN)"

def test_ant_colony():
    gen = AntColonyOptimizationGenerator()
    seed, metrics = gen.generate(bit_length=128, num_ants=5, iterations=5)
    
    assert isinstance(seed, bytes)
    assert len(seed) == 16
    assert "time_ms" in metrics
    assert metrics["algorithm"] == "Ant Colony Optimization (ACO)"
