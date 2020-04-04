"""This module provides a class for representing subgraph matching problems."""
import numpy as np

from .matching_utils import inspect_channels, MonotoneArray, \
    feature_disagreements


class MatchingProblem:
    """A class representing any subgraph matching problem, noisy or otherwise.

    TODO: describe the class in more detail.
    TODO: optionally accept ground truth map argument.
    TODO: Is it okay to describe the tmplt and world attributes using the same
    descriptions as were used for the corresponding parameters?
    TODO: Introduce local_cost threshold.

    Examples
    --------
    >>> tmplt = uclasm.load_edgelist(template_filepath)
    >>> world = uclasm.load_edgelist(world_filepath)
    >>> smp = uclasm.MatchingProblem(tmplt, world)

    Parameters
    ----------
    tmplt : Graph
        Template graph to be matched.
    world : Graph
        World graph to be searched.
    fixed_costs : 2darray, optional
        Cost of assigning a template node to a world node, ignoring structure.
        One row for each template node, one column for each world node.
    local_costs : 2darray, optional
        Initial local costs.
    global_costs : 2darray, optional
        Initial global costs.
    local_cost_threshold : int, optional
        A template node cannot be assigned to a world node if it will result
        in more than this number of its edges missing in an eventual match.
    global_cost_threshold : int, optional
        A subgraph whose cost againt the template exceeds this threshold will
        not be considered a match. It can also be used to eliminate candidates
        from the world graph. A cost of 0 corresponds to an exact match for the
        template, whereas a cost of 1 means that the match may be missing a
        single edge which is present in the template but not in the world.
    ground_truth_provided : bool, optional
        A flag indicating whether a signal has been injected into the world
        graph with node identifiers that match those in the template.
    candidate_print_limit : int, optional
        When summarizing the candidates of each template node, limit the list
        of candidates to this many.

    Attributes
    ----------
    tmplt : Graph
        Template graph to be matched.
    world : Graph
        World graph to be searched.
    shape : (int, int)
        Size of the matching problem: Number of template nodes and world nodes.
    local_cost_threshold : int, optional
        A template node cannot be assigned to a world node if it will result
        in more than this number of its edges missing.
    global_cost_threshold : int, optional
        A subgraph whose cost againt the template exceeds this threshold will
        not be considered a match. It can also be used to eliminate candidates
        from the world graph. A cost of 0 corresponds to an exact match for the
        template, whereas a cost of 1 means that the match may be missing a
        single edge which is present in the template but not in the world.
    """

    def __init__(self,
                 tmplt, world,
                 fixed_costs=None,
                 local_costs=None,
                 global_costs=None,
                 local_cost_threshold=0,
                 global_cost_threshold=0,
                 ground_truth_provided=False,
                 candidate_print_limit=10):

        # Various important matrices will have this shape.
        self.shape = (tmplt.n_nodes, world.n_nodes)

        if fixed_costs is None:
            fixed_costs = np.zeros(self.shape)

        if local_costs is None:
            local_costs = np.zeros(self.shape)

        if global_costs is None:
            global_costs = np.zeros(self.shape)

        # Make sure graphs have the same channels in the same order.
        if tmplt.channels != world.channels:
            inspect_channels(tmplt, world)
            world = world.channel_subgraph(tmplt.channels)

        # Account for self edges in fixed costs.
        if tmplt.has_loops:
            fixed_costs += feature_disagreements(
                tmplt.self_edges,
                world.self_edges
            )
            tmplt = tmplt.loopless_subgraph()
            world = world.loopless_subgraph()

        self._fixed_costs = fixed_costs.view(MonotoneArray)
        self._local_costs = local_costs.view(MonotoneArray)
        self._global_costs = global_costs.view(MonotoneArray)

        # No longer care about self-edges because they are fixed costs.
        self.tmplt = tmplt
        self.world = world

        self.local_cost_threshold = local_cost_threshold
        self.global_cost_threshold = global_cost_threshold

        self._ground_truth_provided = ground_truth_provided
        self._candidate_print_limit = candidate_print_limit

        self._num_valid_candidates = 0

    def copy(self):
        """Returns a copy of the MatchingProblem."""
        return MatchingProblem(self.tmplt.copy(), self.world.copy(),
            fixed_costs=self._fixed_costs.copy(),
            local_costs=self._local_costs.copy(),
            global_costs=self._global_costs.copy(),
            local_cost_threshold=self.local_cost_threshold,
            global_cost_threshold=self.global_cost_threshold,
            ground_truth_provided=self._ground_truth_provided,
            candidate_print_limit=self._candidate_print_limit)

    def set_costs(self, fixed_costs=None, local_costs=None, global_costs=None):
        """Set the cost arrays by force. Override monotonicity.

        Parameters
        ----------
        fixed_costs : 2darray, optional
        local_costs : 2darray, optional
        global_costs : 2darray, optional

        """
        if fixed_costs is not None:
            self._fixed_costs = fixed_costs.view(MonotoneArray)

        if local_costs is not None:
            self._local_costs = local_costs.view(MonotoneArray)


        if global_costs is not None:
            self._global_costs = global_costs.view(MonotoneArray)

    def _have_candidates_changed(self):
        """Check if there are more nodes ruled out as invalid candidates.

        Returns
        -------
        bool
            True if any of the node-node pairs have been set to infinity since
            last time this function was called. False otherwise.
        """
        num_valid_candidates = self._num_valid_candidates
        self._num_valid_candidates = np.count_nonzero(self.structural_costs!=np.Inf)
        return num_valid_candidates != self._num_valid_candidates

    @property
    def fixed_costs(self):
        """2darray: Fixed costs such as node attribute mismatches.

        Cost of assigning a template node to a world node, ignoring structure.
        One row for each template node, one column for each world node.
        TODO: Better docstrings.
        """
        return self._fixed_costs

    @fixed_costs.setter
    def fixed_costs(self, value):
        self._fixed_costs[:] = value

    @property
    def local_costs(self):
        """2darray: Local costs such as missing edges around each node.

        Each entry of this matrix denotes a bound on the local cost of matching
        the template node corresponding to the row to the world node
        corresponding to the column.
        TODO: Better docstrings.
        """
        return self._local_costs

    @local_costs.setter
    def local_costs(self, value):
        self._local_costs[:] = value

    @property
    def global_costs(self):
        """2darray: Costs of full graph match.

        Each entry of this matrix bounds the global cost of matching
        the template node corresponding to the row to the world node
        corresponding to the column.
        TODO: Better docstrings.
        """
        return self._global_costs

    @global_costs.setter
    def global_costs(self, value):
        self._global_costs[:] = value

    def candidates(self):
        """Get the matrix of compatibility between template and world nodes.

        World node j is considered to be a candidate for a template node i if
        there exists an assignment from template nodes to world nodes in which
        i is assigned to j whose cost does not exceed the desired threshold.

        This could be a property, but it is not particularly cheap to compute.

        Returns
        -------
        2darray
            A boolean matrix where each entry indicates whether the world node
            corresponding to the column is a candidate for the template node
            corresponding to the row.
        """
        return self.global_costs <= self.global_cost_threshold

    def __str__(self):
        """Summarize the state of the matching problem.

        Returns
        -------
        str
            Information includes number of candidates for each template node,
            number of template nodes which have exactly one candidate,
            and size of the template and world graphs.
        """
        # Append info strings to this list throughout the function.
        info_strs = []

        info_strs.append("There are {} template nodes and {} world nodes."
                         .format(self.tmplt.n_nodes, self.world.n_nodes))

        # Wouldn't want to recompute this too often.
        candidates = self.candidates()

        # Number of candidates for each template node.
        cand_counts = candidates.sum(axis=1)

        # TODO: if multiple nodes have the same candidates, condense them.

        # Iterate over template nodes in decreasing order of candidates.
        for idx in np.flip(np.argsort(cand_counts)):
            node = self.tmplt.nodes[idx]
            cands = sorted(self.world.nodes[candidates[idx]])
            n_cands = len(cands)

            if n_cands == 1:
                continue

            if n_cands > self._candidate_print_limit:
                cands = cands[:self._candidate_print_limit] + ["..."]

            # TODO: abstract out the getting and setting before and after
            info_strs.append("{} has {} candidates: {}"
                             .format(node, n_cands, ", ".join(cands)))

        # Nodes that have only one candidate
        identified = list(self.tmplt.nodes[cand_counts == 1])
        n_found = len(identified)

        # If there are any nodes that have only one candidate, that is
        # important information and should be recorded.
        if n_found:
            info_strs.append("{} template nodes have 1 candidate: {}"
                             .format(n_found, ", ".join(identified)))

        # This message is useful for debugging datasets for which you have
        # a ground truth signal.
        if self._ground_truth_provided:
            # Assuming ground truth nodes have same names, get the nodes for
            # which ground truth identity is not a candidate
            missing_ground_truth = [
                node for idx, node in enumerate(self.tmplt.nodes)
                if node not in self.world.nodes[candidates[idx]]
            ]
            n_missing = len(missing_ground_truth)

            info_strs.append("{} nodes are missing ground truth candidate: {}"
                             .format(n_missing, missing_ground_truth))

        return "\n".join(info_strs)

    def reduce_world(self):
        """Reduce the size of the world graph.

        Check whether there are any world nodes that are not candidates to
        any tmplt nodes. If so, remove them from the world graph and update
        the matching problem.

        Returns
        -------
        bool
            True if the size of the world is reduced. False otherwise.
        """
        is_cands = np.where(self.structural_costs.min(axis=0) != np.Inf)[0]

        if len(is_cands) > 0:
            self.world = self.world.node_subgraph(is_cands)

            # Update parameters based on new world
            self.structural_costs = self.structural_costs[:, is_cands]
            self.fixed_costs = self.fixed_costs[:, is_cands]
            self._structural_cost_sum = self.structural_costs.sum()
            self._total_costs = self._compute_total_costs()
            return True
        else:
            return False
