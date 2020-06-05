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
    candidates = smp.candidates()

    if smp.edge_attr_fn is None:
        for src_idx, dst_idx in smp.tmplt.nbr_idx_pairs:
            if changed_cands is not None:
                # If neither the source nor destination has changed, there is no
                # point in filtering on this pair of nodes
                if not (changed_cands[src_idx] or changed_cands[dst_idx]):
                    continue

            # get indicators of candidate nodes in the world adjacency matrices
            src_is_cand = candidates[src_idx]
            dst_is_cand = candidates[dst_idx]
            if ~np.any(src_is_cand) or ~np.any(dst_is_cand):
                print("No candidates for given nodes, skipping edge")
                continue

            # This sparse matrix stores the number of supported template edges
            # between each pair of candidates for src and dst
            # i.e. the number of template edges between src and dst that also exist
            # between their candidates in the world
            supported_edges = None

            # Number of total edges in the template between src and dst
            total_tmplt_edges = 0
            for tmplt_adj, world_adj in iter_adj_pairs(smp.tmplt, smp.world):
                tmplt_adj_val = tmplt_adj[src_idx, dst_idx]
                total_tmplt_edges += tmplt_adj_val

                # if there are no edges in this channel of the template, skip it
                if tmplt_adj_val == 0:
                    continue

                # sub adjacency matrix corresponding to edges from the source
                # candidates to the destination candidates
                world_sub_adj = world_adj[:, dst_is_cand][src_is_cand, :]

                # Edges are supported up to the number of edges in the template
                if supported_edges is None:
                    supported_edges = world_sub_adj.minimum(tmplt_adj_val)
                else:
                    supported_edges += world_sub_adj.minimum(tmplt_adj_val)

            src_support = supported_edges.max(axis=1)
            src_least_cost = total_tmplt_edges - src_support.A

            # Different algorithm from REU
            # Main idea: assigning u' to u and v' to v causes cost for u to increase
            # based on minimum between cost of v and missing edges between u and v
            # src_least_cost = np.maximum(total_tmplt_edges - supported_edges.A,
            #                             local_costs[dst_idx][dst_is_cand]).min(axis=1)

            src_least_cost = np.array(src_least_cost).flatten()
            # Update the local cost bound
            new_local_costs[src_idx][src_is_cand] += src_least_cost

            if src_idx != dst_idx:
                dst_support = supported_edges.max(axis=0)
                dst_least_cost = total_tmplt_edges - dst_support.A
                dst_least_cost = np.array(dst_least_cost).flatten()
                new_local_costs[dst_idx][dst_is_cand] += dst_least_cost
    else:
        # Iterate over template edges and consider best matches for world edges

        src_col = smp.tmplt.source_col
        dst_col = smp.tmplt.target_col
        tmplt_edgelist = smp.tmplt.edgelist
        tmplt_attr_keys = [attr for attr in smp.tmplt.edgelist.columns if attr not in [src_col, dst_col]]
        tmplt_srcs = tmplt_edgelist[src_col]
        tmplt_dsts = tmplt_edgelist[dst_col]
        tmplt_attr_cols = [tmplt_edgelist[key] for key in tmplt_attr_keys]
        for src_node, dst_node, *tmplt_attrs in zip(tmplt_srcs, tmplt_dsts, *tmplt_attr_cols):
            src_col = smp.tmplt.source_col
            dst_col = smp.tmplt.target_col
            tmplt_attrs_dict = dict(zip(tmplt_attr_keys, tmplt_attrs))
            # Get candidates for src and dst
            src_idx = smp.tmplt.node_idxs[src_node]
            dst_idx = smp.tmplt.node_idxs[dst_node]
            src_node, dst_node = str(src_node), str(dst_node)
            if changed_cands is not None:
                # If neither the source nor destination has changed, there is no
                # point in filtering on this pair of nodes
                if not (changed_cands[src_idx] or changed_cands[dst_idx]):
                    continue
            # Matrix of costs of assigning template node src_idx and dst_idx
            # to candidates row_idx and col_idx
            assignment_costs = np.zeros(smp.shape)
            missing_edge_cost = smp.missing_edge_cost_fn((src_node, dst_node))
            assignment_costs[src_idx, :] = missing_edge_cost
            assignment_costs[dst_idx, :] = missing_edge_cost

            # TODO: add some data to the graph classes to store the node indexes
            # of the source and destination of each edge. You can then use this
            # to efficiently get your masks by:
            # >>> candidates[src_idx, smp.world.src_idxs]
            src_cands = smp.world.nodes[candidates[src_idx]]
            dst_cands = smp.world.nodes[candidates[dst_idx]]
            # cand_edge_src_mask = smp.world.edgelist[src_col].isin(src_cands)

            world_edge_srcs = smp.world.edgelist[src_col]
            world_edge_src_idxs = [smp.world.node_idxs[source] for source in world_edge_srcs]
            cand_edge_src_mask = candidates[src_idx, world_edge_src_idxs]
            cand_edgelist = smp.world.edgelist[cand_edge_src_mask]
            cand_edge_dsts = cand_edgelist[src_col]
            cand_edge_dst_idxs = [smp.world.node_idxs[dst] for dst in cand_edge_dsts]
            # cand_edge_dst_mask = cand_edgelist[dst_col].isin(dst_cands)
            cand_edgelist = cand_edgelist[cand_edge_dst_mask]
            cand_edge_dst_mask = candidates[dst_idx, cand_edge_dst_idxs]

            cand_attr_keys = [attr for attr in cand_edgelist.columns if attr not in [src_col, dst_col]]
            src_cands = cand_edgelist[src_col]
            dst_cands = cand_edgelist[dst_col]
            attr_cols = [cand_edgelist[key] for key in cand_attr_keys]

            for src_cand, dst_cand, *cand_attrs in zip(src_cands, dst_cands, *attr_cols):
                src_cand_idx = smp.world.node_idxs[src_cand]
                dst_cand_idx = smp.world.node_idxs[dst_cand]
                src_cand, dst_cand = str(src_cand), str(dst_cand)
                cand_attrs_dict = dict(zip(cand_attr_keys, cand_attrs))
                attr_cost = smp.edge_attr_fn((src_node, dst_node), (src_cand, dst_cand), tmplt_attrs_dict, cand_attrs_dict)
                assignment_costs[src_idx, src_cand_idx] = min(assignment_costs[src_idx, src_cand_idx], attr_cost)
                assignment_costs[dst_idx, dst_cand_idx] = min(assignment_costs[dst_idx, dst_cand_idx], attr_cost)

            new_local_costs += assignment_costs

    return new_local_costs

def edgewise(smp, changed_cands=None):
    """Bound local assignment costs by edge disagreements between candidates.

    Parameters
    ----------
    smp : MatchingProblem
        A subgraph matching problem on which to compute edgewise cost bounds.
    """
    smp.local_costs = edgewise_local_costs(smp, changed_cands)
