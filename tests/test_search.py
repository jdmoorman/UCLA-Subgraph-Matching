"""Tests for the search functions."""
import pytest
import uclasm
from uclasm import Graph, MatchingProblem
from uclasm.matching.search import *
from uclasm.matching.cost_bounds import *

import numpy as np
from scipy.sparse import csr_matrix
import pandas as pd


@pytest.fixture
def smp():
    """Create a subgraph matching problem."""
    adj0 = csr_matrix([[0, 0, 0],
                       [1, 0, 0],
                       [0, 0, 0]])
    adj1 = csr_matrix([[0, 0, 0],
                       [0, 0, 0],
                       [0, 1, 0]])
    nodelist = pd.DataFrame(['a', 'b', 'c'], columns=[Graph.node_col])
    edgelist = pd.DataFrame([['b', 'a', 'c1'],
                             ['c', 'b', 'c2']], columns=[Graph.source_col,
                                                   Graph.target_col,
                                                   Graph.channel_col])
    tmplt = Graph([adj0, adj1], ['c1', 'c2'], nodelist, edgelist)
    world = Graph([adj0, adj1], ['c1', 'c2'], nodelist, edgelist)
    smp = MatchingProblem(tmplt, world)
    return smp

@pytest.fixture
def smp_noisy():
    """Create a noisy subgraph matching problem."""
    adj0 = csr_matrix([[0, 0, 0],
                       [1, 0, 0],
                       [0, 0, 0]])
    adj1 = csr_matrix([[0, 0, 0],
                       [0, 0, 0],
                       [0, 1, 0]])
    nodelist = pd.DataFrame(['a', 'b', 'c'], columns=[Graph.node_col])
    edgelist = pd.DataFrame([['b', 'a', 'c1'],
                             ['c', 'b', 'c2']], columns=[Graph.source_col,
                                                   Graph.target_col,
                                                   Graph.channel_col])
    tmplt = Graph([adj0, adj1], ['c1', 'c2'], nodelist, edgelist)
    adj2 = csr_matrix(np.zeros((3,3)))
    edgelist2 = pd.DataFrame([['b', 'a', 'c1']], columns=[Graph.source_col,
                                                   Graph.target_col,
                                                   Graph.channel_col])
    world = Graph([adj0.copy(), adj2], ['c1', 'c2'], nodelist, edgelist2)
    smp = MatchingProblem(tmplt, world, global_cost_threshold=1)
    return smp

class TestGreedySearch:
    """Tests related to the greedy search """
    def test_greedy_search(self, smp):
        nodewise_cost_bound(smp)
        edgewise_cost_bound(smp)
        solutions = greedy_best_k_matching(smp)
        assert len(solutions) == 1

    def test_greedy_search_noisy(self, smp_noisy):
        nodewise_cost_bound(smp_noisy)
        edgewise_cost_bound(smp_noisy)
        solutions = greedy_best_k_matching(smp_noisy)
        assert len(solutions) == 1
        assert solutions[0].cost == 1
        for i in range(3):
            assert dict(solutions[0].matching)[i] == i

    def test_greedy_search_noisy_high_thresh(self, smp_noisy):
        smp_noisy.global_cost_threshold = float("inf")
        nodewise_cost_bound(smp_noisy)
        edgewise_cost_bound(smp_noisy)
        solutions = greedy_best_k_matching(smp_noisy)
        assert len(solutions) == 1
        assert solutions[0].cost == 1
        for i in range(3):
            assert dict(solutions[0].matching)[i] == i
        solutions = greedy_best_k_matching(smp_noisy, k=6)
        assert len(solutions) == 6
        assert solutions[0].cost == 1
        for i in range(3):
            assert dict(solutions[0].matching)[i] == i
        solutions = greedy_best_k_matching(smp_noisy, k=5)
        assert len(solutions) == 5
        assert solutions[0].cost == 1
        for i in range(3):
            assert dict(solutions[0].matching)[i] == i