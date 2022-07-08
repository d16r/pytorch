import torch
import torch.nn.functional as F
from .expanded_weights_impl import implements_per_sample_grads
from .expanded_weights_utils import \
    forward_helper, set_grad_sample_if_exists, unpack_expanded_weight_or_tensor
from typing import List, Optional

@implements_per_sample_grads(F.linear)
class LinearPerSampleGrad(torch.autograd.Function):
    @staticmethod
    def forward(ctx, _, __, *expanded_args_and_kwargs):
        if len(expanded_args_and_kwargs[0].shape) <= 1:
            raise RuntimeError("Input does not have a batch dimension. Expanded Weights expected input "
                               f"of at least rank 2, got of rank {len(expanded_args_and_kwargs[0].shape)}")
        expanded_kwargs = {'bias': expanded_args_and_kwargs[2] if len(expanded_args_and_kwargs) == 3 else None}
        expanded_args = expanded_args_and_kwargs[:2]
        output = forward_helper(F.linear, expanded_args, expanded_kwargs)
        ctx.args = expanded_args
        ctx.kwargs = expanded_kwargs
        return output

    @staticmethod
    def backward(ctx, grad_output):
        input, weight = ctx.args
        bias = ctx.kwargs['bias']
        results: List[Optional[torch.Tensor]] = []
        results.append(None)  # for kwarg_names
        results.append(None)  # for op reference

        if input.requires_grad:
            results.append(grad_output.matmul(unpack_expanded_weight_or_tensor(weight)))
        else:
            results.append(None)
        results.extend([None] * 2)  # weight and bias don't compute batched gradients

        # weight and bias get their grad_sample fields set directly if they exist
        set_grad_sample_if_exists(weight, grad_output, lambda _, go: torch.einsum("n...i,n...j->nij", go, input))
        set_grad_sample_if_exists(bias, grad_output, lambda _, go: torch.einsum("n...k->nk", go))
        return tuple(results)
