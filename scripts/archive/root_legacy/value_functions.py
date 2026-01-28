import numpy as np
import math
from typing import Dict, Any, Literal, Union, Optional
from dataclasses import dataclass
from enum import Enum

class FunctionType(Enum):
    """Supported value function types."""
    LINEAR = "linear"
    POLYNOMIAL = "polynomial"
    EXPONENTIAL = "exponential"
    LOGARITHMIC = "logarithmic"
    PIECEWISE = "piecewise"

class CriterionDirection(Enum):
    """Direction of preference for criteria."""
    INCREASING = "increasing"  # Higher raw values are better
    DECREASING = "decreasing"  # Lower raw values are better

@dataclass
class CriterionConfig:
    """Configuration for a single criterion."""
    min_val: float
    max_val: float
    direction: CriterionDirection
    description: str = ""
    units: str = ""

    @property
    def range(self) -> float:
        return self.max_val - self.min_val

    def normalize(self, x: float, allow_extrapolation: bool = True) -> float:
        """
        Normalize raw value to [0,1] range based on direction.
        If allow_extrapolation=True, values outside min/max can produce results outside [0,1].
        """
        if self.direction == CriterionDirection.DECREASING:
            # Lower is better
            return (self.max_val - x) / self.range
        else:
            # Higher is better
            return (x - self.min_val) / self.range

class ValueFunction:
    """Base class for value functions."""

    def __init__(self, func_type: FunctionType, **params):
        self.func_type = func_type
        self.params = params
        self._validate_params()

    def _validate_params(self):
        """Validate function parameters. Override in subclasses."""
        pass

    def transform(self, x_norm: float) -> float:
        """
        Transform normalized value [0,1] to value score [0,1].

        Args:
            x_norm: Normalized input value (can be outside [0,1] for extrapolation)

        Returns:
            Value score (can be outside [0,1] for extrapolation)
        """
        raise NotImplementedError

    def __call__(self, x_norm: float) -> float:
        """Make function callable."""
        return self.transform(x_norm)

class LinearFunction(ValueFunction):
    """Linear transformation: v(x) = x."""

    def __init__(self):
        super().__init__(FunctionType.LINEAR)

    def transform(self, x_norm: float) -> float:
        return x_norm

class PolynomialFunction(ValueFunction):
    """
    Power function: v(x) = x^a

    a < 1: concave (diminishing returns)
    a > 1: convex (accelerating returns)
    a = 1: linear
    """

    def __init__(self, a: float = 1.0):
        super().__init__(FunctionType.POLYNOMIAL, a=a)
        self.a = a

    def _validate_params(self):
        if self.a <= 0:
            raise ValueError(f"Polynomial exponent must be > 0, got {self.a}")

    def transform(self, x_norm: float) -> float:
        # Handle negative values for polynomial
        if x_norm < 0:
            # For negative values, we might want to extend smoothly
            # Using sign preservation for odd roots when appropriate
            if self.a.is_integer() and self.a % 2 == 1:
                return -((-x_norm) ** self.a)
            else:
                # For non-integer exponents, use absolute value
                return (abs(x_norm) ** self.a) * (1 if x_norm >= 0 else -1)
        return x_norm ** self.a

class ExponentialFunction(ValueFunction):
    """
    Exponential function: v(x) = (1 - exp(a * x)) / (1 - exp(a))

    a < 0: concave (diminishing returns)
    a > 0: convex (accelerating returns)
    """

    def __init__(self, a: float = 1.0):
        super().__init__(FunctionType.EXPONENTIAL, a=a)
        self.a = a

    def transform(self, x_norm: float) -> float:
        if abs(self.a) < 1e-10:
            # Small a approximates linear
            return x_norm

        denominator = 1 - math.exp(self.a)
        if abs(denominator) < 1e-10:
            # Avoid division by zero - use linear approximation
            return x_norm

        return (1 - math.exp(self.a * x_norm)) / denominator

class LogarithmicFunction(ValueFunction):
    """
    Logarithmic function: v(x) = log(a * x + 1) / log(a + 1)

    a > 0: concave (diminishing returns)
    """

    def __init__(self, a: float = 1.0):
        super().__init__(FunctionType.LOGARITHMIC, a=a)
        self.a = a

    def _validate_params(self):
        if self.a <= -1:
            raise ValueError(f"Logarithmic parameter must be > -1, got {self.a}")

    def transform(self, x_norm: float) -> float:
        if abs(self.a + 1) < 1e-10:
            # Special case: a = -1, use linear
            return x_norm

        # Handle case where argument might be non-positive
        argument = self.a * x_norm + 1
        if argument <= 0:
            # Extrapolate linearly for very negative values
            # This maintains monotonicity
            slope = self.a / (math.log(self.a + 1) * (self.a + 1))
            intercept = -slope * (1 / self.a)
            return slope * x_norm + intercept

        return math.log(argument) / math.log(self.a + 1)

class PiecewiseFunction(ValueFunction):
    """
    Piecewise linear function with threshold.

    v(x) = slope_low * x for x < threshold
    v(x) = intercept + slope_high * (x - threshold) for x >= threshold
    """

    def __init__(self, threshold: float = 0.5, slope_low: float = 0.5, slope_high: float = 0.5):
        super().__init__(FunctionType.PIECEWISE,
                        threshold=threshold,
                        slope_low=slope_low,
                        slope_high=slope_high)
        self.threshold = threshold
        self.slope_low = slope_low
        self.slope_high = slope_high
        self.intercept = slope_low * threshold

    def _validate_params(self):
        if not 0 < self.threshold < 1:
            raise ValueError(f"Threshold must be in (0,1), got {self.threshold}")
        if self.slope_low < 0 or self.slope_high < 0:
            raise ValueError("Slopes must be non-negative")

    def transform(self, x_norm: float) -> float:
        if x_norm < self.threshold:
            return self.slope_low * x_norm
        else:
            return self.intercept + self.slope_high * (x_norm - self.threshold)

class ValueFunctionFactory:
    """Factory for creating value functions from specifications."""

    @staticmethod
    def from_spec(spec: str) -> ValueFunction:
        """
        Create value function from specification string.

        Format: "type, param1=value1, param2=value2, ..."
        Example: "polynomial, a=0.5"
        Example: "exponential, a=1.2"
        """
        parts = [p.strip() for p in spec.split(',')]
        func_type = FunctionType(parts[0].lower())

        # Parse parameters
        params = {}
        for part in parts[1:]:
            if '=' in part:
                key, value = part.split('=')
                params[key.strip()] = float(value.strip())

        return ValueFunctionFactory.create(func_type, **params)

    @staticmethod
    def create(func_type: FunctionType, **params) -> ValueFunction:
        """Create value function with given type and parameters."""
        if func_type == FunctionType.LINEAR:
            return LinearFunction()
        elif func_type == FunctionType.POLYNOMIAL:
            return PolynomialFunction(**params)
        elif func_type == FunctionType.EXPONENTIAL:
            return ExponentialFunction(**params)
        elif func_type == FunctionType.LOGARITHMIC:
            return LogarithmicFunction(**params)
        elif func_type == FunctionType.PIECEWISE:
            return PiecewiseFunction(**params)
        else:
            raise ValueError(f"Unknown function type: {func_type}")

class MAVTValueTransformer:
    """
    Main transformer for MAVT applications with built-in reference ranges.
    """

    # Reference ranges from literature (as per your specification)
    REFERENCE_RANGES = {
        'energy_cost': {
            'min': 0.47,  # 5th percentile from dataset
            'max': 3.31,  # 95th percentile from dataset
            'direction': CriterionDirection.DECREASING,
            'description': 'Daily cooling cost ($)',
            'reference': """
                Huyen & Cetin (2019): 2.0 kWh baseline × $0.14/kWh = $0.28
                Kim et al. (2024): 82°F setpoint reduces by 48% → $0.15
                Cetin & Novoselac (2015): Partial operation adjustment → $0.47
                Alves et al. (2016): Degraded systems consume 2.5-4× more
                Krarti & Howarth (2020): Low-efficiency systems → $3.31
            """
        },
        'environmental': {
            'min': 2.19,   # Derived from energy bounds
            'max': 15.45,  # Derived from energy bounds
            'direction': CriterionDirection.DECREASING,
            'description': 'Daily CO₂ emissions (lbs)',
            'reference': """
                EPA eGRID (2023): PA grid emissions 0.6458 lbs CO₂/kWh
                Min: (0.47 / 0.14) × 8h × 0.6458 = 2.19 lbs
                Max: (3.31 / 0.14) × 8h × 0.6458 = 15.45 lbs
            """
        },
        'comfort': {
            'min': 0.0,
            'max': 10.0,
            'direction': CriterionDirection.INCREASING,
            'description': 'Comfort score (0-10)',
            'units': 'points'
        },
        'practicality': {
            'min': 1.5,
            'max': 10.0,
            'direction': CriterionDirection.INCREASING,
            'description': 'Practicality score (1.5-10)',
            'units': 'points'
        }
    }

    def __init__(self, output_scale: float = 10.0):
        """
        Args:
            output_scale: Scale output to [0, output_scale] (default: 10.0)
        """
        self.output_scale = output_scale
        self._configs = {}
        self._value_functions = {}

        # Initialize configurations
        for key, config_data in self.REFERENCE_RANGES.items():
            self._configs[key] = CriterionConfig(
                min_val=config_data['min'],
                max_val=config_data['max'],
                direction=CriterionDirection(config_data['direction']),
                description=config_data.get('description', ''),
                units=config_data.get('units', '')
            )

    def add_criterion(self, name: str, config: CriterionConfig):
        """Add or override a criterion configuration."""
        self._configs[name] = config

    def set_value_function(self, criterion: str, func_spec: Union[str, ValueFunction]):
        """Set value function for a criterion."""
        if isinstance(func_spec, str):
            self._value_functions[criterion] = ValueFunctionFactory.from_spec(func_spec)
        else:
            self._value_functions[criterion] = func_spec

    def transform(self, criterion: str, raw_value: float,
                  allow_extrapolation: bool = True) -> float:
        """
        Transform raw criterion value to normalized score.

        Args:
            criterion: Criterion name (must be in configurations)
            raw_value: Raw criterion value
            allow_extrapolation: Whether to allow values outside reference range

        Returns:
            Transformed score in [0, output_scale]
        """
        # Get configuration
        if criterion not in self._configs:
            raise ValueError(f"Unknown criterion: {criterion}. "
                           f"Available: {list(self._configs.keys())}")

        config = self._configs[criterion]

        # Normalize based on direction
        x_norm = config.normalize(raw_value, allow_extrapolation)

        # Apply value function (default to linear if not specified)
        value_func = self._value_functions.get(criterion, LinearFunction())
        score = value_func.transform(x_norm)

        # Scale to output range and clamp to [0, output_scale]
        scaled_score = score * self.output_scale
        return max(0.0, min(self.output_scale, scaled_score))

    def batch_transform(self, criterion: str, raw_values: np.ndarray,
                       allow_extrapolation: bool = True) -> np.ndarray:
        """Transform multiple values at once."""
        return np.vectorize(lambda x: self.transform(criterion, x, allow_extrapolation))(raw_values)

    def get_criterion_info(self, criterion: str) -> Dict[str, Any]:
        """Get information about a criterion."""
        if criterion not in self._configs:
            raise ValueError(f"Unknown criterion: {criterion}")

        config = self._configs[criterion]
        func = self._value_functions.get(criterion, LinearFunction())

        return {
            'name': criterion,
            'min': config.min_val,
            'max': config.max_val,
            'direction': config.direction.value,
            'description': config.description,
            'units': config.units,
            'value_function': func.func_type.value,
            'function_params': func.params
        }