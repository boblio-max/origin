"""OSPR - Opposite Seesaw Parameter Reduction.

Replaces the dense weight matrix of a Linear (or Conv2d) layer with a set of
seesaw angles, one per pair of weights, plus a single half-length that is
shared across every OSPR layer in the model.

For a pair (w_a, w_b) represented by angle theta and shared half-length L:

    w_a = L * sin(theta)
    w_b = L * cos(theta)

So two weights are stored as one learned angle, and the only extra parameter
(L) is shared globally. Backprop only updates the angles and the half-length.

apply_ospr(model) walks a transformers/torch model, swaps every nn.Linear for
an OSPRLinear (each holding a reference to one shared OSPRParams), and returns
the same torch.nn.Module. The shared half-length is registered once as a
submodule of every OSPR layer, so torch counts it a single time.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from collections import Counter


class OSPRParams(nn.Module):
    """Holds the single half-length parameter shared by all OSPR layers."""

    def __init__(self, init_value=1.0):
        super().__init__()
        self.half_length = nn.Parameter(torch.tensor(float(init_value)))

    def __repr__(self):
        return f"OSPRParams(half_length={self.half_length.item():.4f})"


class OSPRLinear(nn.Module):
    """Linear layer whose weight is reconstructed from OSPR angles + shared half-length.

    Weights are paired by a fixed random permutation (a buffer), so the two
    weights produced by one angle are random weights in the layer.
    """

    def __init__(self, in_features, out_features, osp_params, bias=True):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.osp_params = osp_params

        numel = in_features * out_features
        self.numel = numel
        self.has_odd = numel % 2 == 1
        paired = numel - (1 if self.has_odd else 0)

        self.register_buffer("perm", torch.randperm(paired))
        self.angles = nn.Parameter(torch.randn(paired // 2) * 0.05)

        if self.has_odd:
            self.residual = nn.Parameter(torch.zeros(1))
        else:
            self.residual = None

        if bias:
            self.bias = nn.Parameter(torch.zeros(out_features))
        else:
            self.register_parameter("bias", None)

    def _reconstruct(self):
        L = self.osp_params.half_length
        v = torch.stack([L * torch.sin(self.angles), L * torch.cos(self.angles)], dim=1).reshape(-1)
        flat = v[torch.argsort(self.perm)]
        if self.has_odd:
            flat = torch.cat([flat, self.residual])
        return flat.reshape(self.out_features, self.in_features)

    def forward(self, x):
        return F.linear(x, self._reconstruct(), self.bias)

    @classmethod
    def from_linear(cls, linear, osp_params, seed=None):
        w = linear.weight.detach().reshape(-1)
        numel = w.shape[0]
        has_odd = numel % 2 == 1
        paired = numel - (1 if has_odd else 0)

        gen = torch.Generator().manual_seed(seed) if seed is not None else None
        perm = torch.randperm(paired, generator=gen)

        a = w[perm[0::2]]
        b = w[perm[1::2]]
        mag = torch.hypot(a, b)
        L = mag.mean().clamp_min(1e-8)
        osp_params.half_length.data.copy_(L)

        module = cls.__new__(cls)
        nn.Module.__init__(module)
        module.in_features = linear.in_features
        module.out_features = linear.out_features
        module.osp_params = osp_params
        module.numel = numel
        module.has_odd = has_odd
        module.register_buffer("perm", perm)
        module.angles = nn.Parameter(torch.atan2(a, b))
        if has_odd:
            module.residual = nn.Parameter(w[paired:])
        else:
            module.residual = None
        if linear.bias is not None:
            module.bias = nn.Parameter(linear.bias.detach().clone())
        else:
            module.register_parameter("bias", None)
        return module


class OSPRConv2d(nn.Module):
    """Conv2d layer whose weight is reconstructed from OSPR angles + shared half-length."""

    def __init__(self, in_channels, out_channels, kernel_size, stride=1, padding=0,
                 dilation=1, groups=1, osp_params=None, bias=True):
        super().__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = kernel_size if isinstance(kernel_size, (tuple, list)) else (kernel_size, kernel_size)
        self.stride = stride
        self.padding = padding
        self.dilation = dilation
        self.groups = groups
        self.osp_params = osp_params

        numel = out_channels * in_channels // groups * self.kernel_size[0] * self.kernel_size[1]
        self.numel = numel
        self.has_odd = numel % 2 == 1
        paired = numel - (1 if self.has_odd else 0)

        self.register_buffer("perm", torch.randperm(paired))
        self.angles = nn.Parameter(torch.randn(paired // 2) * 0.05)

        if self.has_odd:
            self.residual = nn.Parameter(torch.zeros(1))
        else:
            self.residual = None

        if bias:
            self.bias = nn.Parameter(torch.zeros(out_channels))
        else:
            self.register_parameter("bias", None)

    def _reconstruct(self):
        L = self.osp_params.half_length
        v = torch.stack([L * torch.sin(self.angles), L * torch.cos(self.angles)], dim=1).reshape(-1)
        flat = v[torch.argsort(self.perm)]
        if self.has_odd:
            flat = torch.cat([flat, self.residual])
        shape = (self.out_channels, self.in_channels // self.groups) + tuple(self.kernel_size)
        return flat.reshape(shape)

    def forward(self, x):
        return F.conv2d(x, self._reconstruct(), self.bias, self.stride, self.padding, self.dilation, self.groups)

    @classmethod
    def from_conv2d(cls, conv, osp_params, seed=None):
        w = conv.weight.detach().reshape(-1)
        numel = w.shape[0]
        has_odd = numel % 2 == 1
        paired = numel - (1 if has_odd else 0)

        gen = torch.Generator().manual_seed(seed) if seed is not None else None
        perm = torch.randperm(paired, generator=gen)

        a = w[perm[0::2]]
        b = w[perm[1::2]]
        mag = torch.hypot(a, b)
        L = mag.mean().clamp_min(1e-8)
        osp_params.half_length.data.copy_(L)

        module = cls.__new__(cls)
        nn.Module.__init__(module)
        module.in_channels = conv.in_channels
        module.out_channels = conv.out_channels
        module.kernel_size = conv.kernel_size if isinstance(conv.kernel_size, (tuple, list)) else (conv.kernel_size, conv.kernel_size)
        module.stride = conv.stride
        module.padding = conv.padding
        module.dilation = conv.dilation
        module.groups = conv.groups
        module.osp_params = osp_params
        module.numel = numel
        module.has_odd = has_odd
        module.register_buffer("perm", perm)
        module.angles = nn.Parameter(torch.atan2(a, b))
        if has_odd:
            module.residual = nn.Parameter(w[paired:])
        else:
            module.residual = None
        if conv.bias is not None:
            module.bias = nn.Parameter(conv.bias.detach().clone())
        else:
            module.register_parameter("bias", None)
        return module


def _replace(module, osp_params, include_conv, seed, shared_param_counts=None):
    count = 0
    for name, child in list(module.named_children()):
        if isinstance(child, OSPRLinear) or isinstance(child, OSPRConv2d):
            continue
        if isinstance(child, nn.Linear):
            weight = getattr(child, "weight", None)
            if weight is not None and shared_param_counts and shared_param_counts.get(id(weight), 0) > 1:
                continue
            setattr(module, name, OSPRLinear.from_linear(child, osp_params, seed=seed))
            count += 1
        elif include_conv and isinstance(child, nn.Conv2d):
            weight = getattr(child, "weight", None)
            if weight is not None and shared_param_counts and shared_param_counts.get(id(weight), 0) > 1:
                continue
            setattr(module, name, OSPRConv2d.from_conv2d(child, osp_params, seed=seed))
            count += 1
        else:
            count += _replace(child, osp_params, include_conv, seed, shared_param_counts)
    return count


class ospr:
    """Origin-facing entry points for the OSPR method."""

    @staticmethod
    def apply_ospr(model, include_conv=False, verbose=True):
        if not isinstance(model, nn.Module):
            raise TypeError("apply_ospr expects a torch.nn.Module (e.g. a transformers model).")

        if any(isinstance(m, (OSPRLinear, OSPRConv2d)) for m in model.modules()):
            if verbose:
                print("[OSPR] model already has OSPR layers applied, skipping.")
            return model

        total_before = sum(p.numel() for p in model.parameters())

        shared_param_counts = Counter()
        for _m in model.modules():
            for _p in _m.parameters(recurse=False):
                shared_param_counts[id(_p)] += 1

        osp_params = OSPRParams()
        replaced = _replace(model, osp_params, include_conv, seed=None, shared_param_counts=shared_param_counts)

        total_after = sum(p.numel() for p in model.parameters())

        if verbose:
            saved = total_before - total_after
            pct = (saved / total_before * 100.0) if total_before else 0.0
            print(f"[OSPR] replaced {replaced} layer(s) with OSPR")
            print(f"[OSPR] parameters: {total_before} -> {total_after}  ({pct:.1f}% reduction)")

        return model

    @staticmethod
    def param_count(model):
        total = sum(p.numel() for p in model.parameters())
        trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
        return total, trainable


