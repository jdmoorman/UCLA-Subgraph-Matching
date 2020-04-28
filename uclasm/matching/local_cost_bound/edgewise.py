"""Provide a function for bounding node assignment costs with edgewise info."""
import numpy as np

def iter_adj_pairs(tmplt, world):
    """Generator for pairs of adjacency matrices.

    Each pair of adjacency matrices corresponds to the same channel in both
    the template and the world.

    Parameters
    ----------
    tmplt : Graph
        Template graph to be matched.
    world : Graph
        World graph to be searched.

    Yields
    -------
    (spmatrix, spmatrix)
        A tuple of sparse adjacency matrices
    """
    for channel, tmplt_adj in tmplt.ch_to_adj.items():
        world_adj = world.ch_to_adj[channel]
        yield (tmplt_adj, world_adj)
        yield (tmplt_adj.T, world_adj.T)


def edgewise_local_costs(smp, changed_cands=None):
    """Compute edge disagreements between candidates.

    Computes a lower bound on the local cost of assignment by iterating
    over template edges and comparing candidates for the endpoints.
    The lower bound for an assignment (u, u') is the sum over all neighbors
    v of u of the minimum number of missing edges between (u', v') over
    all v' where v' is a candidate for v.

    TODO: Cite paper from REU.

    Parameters
    ----------
    smp : MatchingProblem
        A subgraph matching problem on which to compute edgewise cost bounds.
    changed_cands : ndarray(bool)
        Boolean array indicating which template nodes have candidates that have
        changed since the last run of the edgewise filter. Only these nodes and
        their neighboring template nodes have to be reevaluated.
    """
    new_local_costs = np.zeros(smp.shape)

    for src_idx, dst_idx in smp.tmplt.nbr_idx_pairs:
        if changed_cands is not None:
            # If neither the source nor destination has changed, there is no
            # point in filtering on this pair of nodes
            if not (changed_cands[src_idx] or changed_cands[dst_idx]):
                continue

        # get indicators of candidate nodes in the world adjacency matrices
        candidates = smp.candidates()
        src_is_cand = candidates[src_idx]
        dst_is_cand = candidates[dst_idx]
        if ~np.any(src_is_cand) or ~np.any(dst_is_cand):
            raise Exception("Error: no candidates for given nodes")

        if smp.edge_attr_fn is None:
            # This sparse matrix stores the number of supported template edges
            # between each pair of candidates for src and dst
            # i.e. the number of template edges between src and dst that also exist
            # between their candidates in the world
            supported_edges = None

            # Number of total edges in the template between src and dst
            total_tmplt_edges = 0
        else:
            # Matrix of costs of assigning template node src_idx and dst_idx
            # to candidates row_idx and col_idx
            assignment_costs = np.zeros((np.sum(src_is_cand), np.sum(dst_is_cand)))
        for tmplt_adj, world_adj in iter_adj_pairs(smp.tmplt, smp.world):
            tmplt_adj_val = tmplt_adj[src_idx, dst_idx]
            if smp.edge_attr_fn is None
                total_tmplt_edges += tmplt_adj_val

            # if there are no edges in this channel of the template, skip it
            if tmplt_adj_val == 0:
                continue

            if smp.edge_attr_fn is None:
                # sub adjacency matrix corresponding to edges from the source
                # candidates to the destination candidates
                world_sub_adj = world_adj[:, dst_is_cand][src_is_cand, :]

                # Edges are supported up to the number of edges in the template
                if supported_edges is None:
                    supported_edges = world_sub_adj.minimum(tmplt_adj_val)
                else:
                    supported_edges += world_sub_adj.minimum(tmplt_adj_val)
            elif tmplt_adj_val == 1:
                tmplt_edge = smp.tmplt.edgelist[(smp.tmplt.edgelist[smp.tmplt.source_col] == smp.tmplt.nodes[src_idx]) & (smp.tmplt.edgelist[smp.tmplt.target_col] == smp.tmplt.nodes[dst_idx])].iloc[0]
                # Iterate over all world edges between candidates for src and dst
                for world_edge_idx, world_edge in smp.world.edgelist[smp.world.edgelist[smp.world.source_col].isin(world.nodes[src_is_cand])&smp.world.edgelist[smp.world.target_col].isin(world.nodes[dst_is_cand])].iterrows():
                    src_cand_idx = smp.world.node_idxs[world_edge[smp.world.source_col]]
                    dst_cand_idx = smp.world.node_idxs[world_edge[smp.world.target_col]]
                    assignment_costs[src_cand_idx, dst_cand_idx] += smp.edge_attr_fn(tmplt_edge, world_edge)
            else:
                raise Exception("More than one template edge between two nodes with attributes is not yet supported.")

        src_support = supported_edges.max(axis=1)
        src_least_cost = total_tmplt_edges - src_support.A
        src_least_cost = np.array(src_least_cost).flatten()

        # Different algorithm from REU
        # Main idea: assigning u' to u and v' to v causes cost for u to increase
        # based on minimum between cost of v and missing edges between u and v
        # src_least_cost = np.maximum(total_tmplt_edges - supported_edges.A,
        #                             local_costs[dst_idx][dst_is_cand]).min(axis=1)

        # Update the local cost bound
        new_local_costs[src_idx][src_is_cand] += src_least_cost

        if src_idx != dst_idx:
            dst_support = supported_edges.max(axis=0)
            dst_least_cost = total_tmplt_edges - dst_support.A
            dst_least_cost = np.array(dst_least_cost).flatten()
            new_local_costs[dst_idx][dst_is_cand] += dst_least_cost

    # Add back in the costs that didn't change and weren't reevaluated
    if changed_cands is not None:
        new_local_costs[changed_cands] = smp.local_costs[changed_cands]

    return new_local_costs

def edgewise(smp, changed_cands=None):
    """Bound local assignment costs by edge disagreements between candidates.

    Parameters
    ----------
    smp : MatchingProblem
        A subgraph matching problem on which to compute edgewise cost bounds.
    """
    smp.local_costs = edgewise_local_costs(smp, changed_cands)
