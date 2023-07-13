# Copyright 2023 Sony Semiconductor Israel, Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

import numpy as np

from mct_quantizers.common.base_inferable_quantizer import mark_quantizer, QuantizationTarget, QuantizerID
from mct_quantizers.common.constants import FOUND_TORCH
from mct_quantizers.common.quant_info import QuantizationMethod
from mct_quantizers.logger import Logger

if FOUND_TORCH:
    import torch
    from mct_quantizers.pytorch.quantizers.base_uniform_inferable_quantizer import BaseUniformInferableQuantizer
    from mct_quantizers.pytorch.quantizer_utils import fix_range_to_include_zero, get_working_device, to_torch_tensor

    @mark_quantizer(quantization_target=QuantizationTarget.Weights,
                    quantization_method=[QuantizationMethod.UNIFORM],
                    identifier=QuantizerID.INFERABLE)
    class WeightsUniformInferableQuantizer(BaseUniformInferableQuantizer):
        """
        Class for quantizing weights using unsigned uniform quantizer.
        """

        def __init__(self,
                     num_bits: int,
                     min_range: np.ndarray,
                     max_range: np.ndarray,
                     per_channel: bool,
                     channel_axis: int = None
                     ):
            """
            Initialize the quantizer with the specified parameters.

            Args:
                num_bits: number of bits to use for quantization
                min_range: min quantization range for quantizing weights
                max_range: max quantization range for quantizing weights
                per_channel: whether to use per-channel quantization
                channel_axis: Axis of input to apply per-channel quantization on.
            """
            super(WeightsUniformInferableQuantizer, self).__init__(num_bits=num_bits,
                                                                   min_range=min_range,
                                                                   max_range=max_range)

            # Align mix/max numpy arrays so they are torch Tensors on the working device
            min_range = to_torch_tensor(min_range).to(get_working_device())
            max_range = to_torch_tensor(max_range).to(get_working_device())

            self.per_channel = per_channel
            self.channel_axis = channel_axis

            min_range, max_range = fix_range_to_include_zero(min_range,
                                                             max_range,
                                                             num_bits)
            # Compute the step size of quantized values.
            self.scales = (max_range - min_range) / (2 ** num_bits - 1)
            self.zero_points = -(
                        min_range / self.scales).int()  # zp has to be positive, and a <=0, so we multiply by -1

            self.scales = self.scales.to(get_working_device())
            self.zero_points = self.zero_points.to(get_working_device())

        def __call__(self,
                     inputs: torch.Tensor) -> torch.Tensor:
            """
            Weight fake quantizer
            Args:
                inputs: weights to quantize.

            Returns:
                quantized weights
            """
            inputs.requires_grad = False
            if self.per_channel:
                return torch.fake_quantize_per_channel_affine(inputs,
                                                              self.scales.flatten(),
                                                              self.zero_points.flatten(),
                                                              axis=self.channel_axis,
                                                              quant_min=self.min_quantized_domain,
                                                              quant_max=self.max_quantized_domain)
            return torch.fake_quantize_per_tensor_affine(inputs,
                                                         self.scales,
                                                         self.zero_points,
                                                         quant_min=self.min_quantized_domain,
                                                         quant_max=self.max_quantized_domain)


else:
    class WeightsUniformInferableQuantizer:  # pragma: no cover
        def __init__(self, *args, **kwargs):
            Logger.error('Installing torch is mandatory '
                         'when using WeightsUniformInferableQuantizer. '
                         'Could not find torch package.')
