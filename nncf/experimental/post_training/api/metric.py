"""
 Copyright (c) 2022 Intel Corporation
 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at
      http://www.apache.org/licenses/LICENSE-2.0
 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""
from typing import Optional, Tuple
import numpy as np

from abc import ABC
from abc import abstractmethod

from nncf.experimental.post_training.api.dataset import NNCFData


class Metric(ABC):
    """
    An abstract class representing an metric.
    """

    def __init__(self):
        self.reset()

    @property
    def value(self):
        """
        Computes metric value for the one dataset sample
        """
        raise NotImplementedError('The value() property should be implemented to use this metric '
                                  'with AccuracyAwareQuantization algorithm!')

    @property
    @abstractmethod
    def avg_value(self):
        """
        Computes metric value across dataset
        """

    @property
    def higher_better(self) -> bool:
        """
        Boolean attribute whether the metric should be increased
        """
        return True

    @abstractmethod
    def update(self, outputs: NNCFData, targets: NNCFData) -> None:
        """
        Calculates and updates metric value

        :param outputs: model output
        :param targets: annotation for metric calculation
        """

    @abstractmethod
    def reset(self) -> None:
        """ Reset metric """


class Accuracy(Metric):

    """
    The classification accuracy metric is defined as the number of correct predictions
    divided by the total number of predictions.
    It measures the proportion of examples for which the predicted label matches the single target label.
    Metric is calculated as a percentage.
    """

    def __init__(self, top_k: int = 1, output_key: Optional[str] = None, target_key: str = "targets"):
        super().__init__()
        self._top_k = top_k
        self._matches = []
        self._output_key = output_key
        self._target_key = target_key

    @property
    def name(self):
        return f'accuracy@top{self._top_k}'

    @property
    def avg_value(self):
        """
        Returns accuracy metric value for all model outputs.
        """
        return {self.name: np.ravel(self._matches).mean()}

    def _extract(self, outputs: NNCFData, targets: NNCFData) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract outputs and targets np.ndarray to compute accuracy
        If output_key is None and the model produces only one tensor,
        it implicitly uses that tensor to compute the model accuracy.
        """
        if self._output_key is None and len(outputs) == 1:
            outputs = list(outputs.values())[0].tensor
        elif self._output_key in outputs:
            outputs = outputs[self._output_key].tensor
        else:
            raise KeyError(
                f"There is no {self._output_key} in the model outputs.")

        if self._target_key in targets:
            targets = targets[self._target_key].tensor
        else:
            raise KeyError(
                f"There is no {self._target_key} in the input data.")

        return outputs, targets

    def update(self, outputs: NNCFData, targets: NNCFData) -> None:
        """
        Updates prediction matches based on the model output value and target.
        To calculate the top@N metric, the model output and target data must be represented
        as a list of length 1 containing vector and scalar values, respectively.

        :param output: 2D model classification output
        [
            [prob_0, ..., prob_M],  # Batch 1
            ...
            [prob_0, ..., prob_M],  # Batch N
        ]
        :param target: 1D annotations
        [
            label_0,    # Batch 1
            ...,
            label_N     # Batch N
        ]
        """
        outputs, targets = self._extract(outputs, targets)

        if outputs.ndim != 2:
            raise ValueError('The accuracy metric should be calculated on 2d outputs. '
                             f'However, the outputs has ndim={outputs.ndim}.')
        if targets.ndim != 1:
            raise ValueError('The accuracy metric should be calculated on 1d targets. '
                             f'However, the targets has ndim={targets.ndim}.')

        preds = np.argpartition(outputs, -self._top_k)[:, -self._top_k:]

        match = np.mean([np.isin(target, pred)
                        for pred, target in zip(preds, targets)])

        self._matches.append(match)

    def reset(self):
        """
        Resets collected matches
        """
        self._matches = []
