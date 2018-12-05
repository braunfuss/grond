import numpy as num
import logging

from pyrocko import gf, util
from pyrocko.guts import String, Float, Dict, Int

from grond.meta import Forbidden, expand_template, Parameter

from ..base import Problem, ProblemConfig

guts_prefix = 'grond'
logger = logging.getLogger('grond.problems.double_rectangular.problem')
km = 1e3
as_km = dict(scale_factor=km, scale_unit='km')


class DoubleRectangularProblemConfig(ProblemConfig):

    ranges = Dict.T(String.T(), gf.Range.T())
    decimation_factor = Int.T(default=1)
    distance_min = Float.T(default=0.)

    def get_problem(self, event, target_groups, targets):
        base_source = gf.DoubleRectangularSource.from_pyrocko_event(
            event,
            anchor1='top',
            decimation_factor=self.decimation_factor)

        subs = dict(
            event_name=event.name,
            event_time=util.time_to_str(event.time))

        problem = DoubleRectangularProblem(
            name=expand_template(self.name_template, subs),
            base_source=base_source,
            distance_min=self.distance_min,
            target_groups=target_groups,
            targets=targets,
            ranges=self.ranges,
            norm_exponent=self.norm_exponent)

        return problem


class DoubleRectangularProblem(Problem):
    # nucleation_x
    # nucleation_y
    # time
    # stf

    problem_parameters = [
        Parameter('east_shift', 'm', label='Easting', **as_km),
        Parameter('north_shift', 'm', label='Northing', **as_km),
        Parameter('depth', 'm', label='Depth', **as_km),
        Parameter('distance', 'm', label='distance', **as_km),
        Parameter('azimuth', 'deg', label='azimuth'),
        Parameter('delta_east', 'm', label='Easting', **as_km),
        Parameter('delta_north', 'm', label='Northing', **as_km),
        Parameter('depth2', 'm', label='Depth2', **as_km),
        Parameter('length1', 'm', label='Length', **as_km),
        Parameter('width1', 'm', label='Width', **as_km),
        Parameter('slip', 'm', label='Slip'),
        Parameter('slip2', 'm', label='Slip'),
        Parameter('strike1', 'deg', label='Strike'),
        Parameter('dip1', 'deg', label='Dip'),
        Parameter('rake1', 'deg', label='Rake'),
        Parameter('length2', 'm', label='Length', **as_km),
        Parameter('width2', 'm', label='Width', **as_km),
        Parameter('strike2', 'deg', label='Strike'),
        Parameter('dip2', 'deg', label='Dip'),
        Parameter('rake2', 'deg', label='Rake')
        ]

    problem_waveform_parameters = [
        Parameter('nucleation_x1', 'offset', label='Nucleation X'),
        Parameter('nucleation_y1', 'offset', label='Nucleation Y'),
        Parameter('nucleation_x2', 'offset', label='Nucleation X'),
        Parameter('nucleation_y2', 'offset', label='Nucleation Y'),
        Parameter('time', 's', label='Time'),
        Parameter('delta_time', 's', label='Time'),
    ]

    dependants = []

    distance_min = Float.T(default=0.0)

    def pack(self, source):
        arr = self.get_parameter_array(source)
        for ip, p in enumerate(self.parameters):
            if p.name == 'time':
                arr[ip] -= self.base_source.time
        return arr

    def get_source(self, x):
        d = self.get_parameter_dict(x)
        p = {}

        for k in self.base_source.keys():
            if k in d:
                p[k] = float(
                    self.ranges[k].make_relative(self.base_source[k], d[k]))

        source = self.base_source.clone(**p)
        return source

    def random_uniform(self, xbounds):
        x = num.zeros(self.nparameters)
        for i in range(self.nparameters):
            x[i] = num.random.uniform(xbounds[i, 0], xbounds[i, 1])

        return x

    def preconstrain(self, x):
        return x

    @classmethod
    def get_plot_classes(cls):
        plots = super(DoubleRectangularProblem, cls).get_plot_classes()
        return plots


__all__ = '''
    DoubleRectangularProblem
    DoubleRectangularProblemConfig
'''.split()
