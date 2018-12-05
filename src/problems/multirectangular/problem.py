import numpy as num
import logging

from pyrocko import gf, util
from pyrocko.guts import String, Float, Dict, Int

from grond.meta import expand_template, Parameter

from ..base import Problem, ProblemConfig

guts_prefix = 'grond'
logger = logging.getLogger('grond.problems.multirectangular.problem')
km = 1e3
as_km = dict(scale_factor=km, scale_unit='km')


class MultiRectangularProblemConfig(ProblemConfig):

    ranges = Dict.T(String.T(), gf.Range.T())
    decimation_factor = Int.T(default=1)
    distance_min = Float.T(default=0.)
    nsources = Int.T(default=1)

    def get_problem(self, event, target_groups, targets):
        base_source = gf.RectangularSource.from_pyrocko_event(
            event,
            anchor='top',
            decimation_factor=self.decimation_factor)

        subs = dict(
            event_name=event.name,
            event_time=util.time_to_str(event.time))

        problem = MultiRectangularProblem(
            name=expand_template(self.name_template, subs),
            base_source=base_source,
            distance_min=self.distance_min,
            target_groups=target_groups,
            targets=targets,
            ranges=self.ranges,
            norm_exponent=self.norm_exponent)

        return problem

from pyrocko.guts import List

km = 1e3

day= 24.*3600.

class CombiSource(gf.Source):
    '''Composite source model.'''

    discretized_source_class = gf.DiscretizedMTSource

    subsources = List.T(gf.Source.T())

    def __init__(self, subsources=[], **kwargs):
        if subsources:

            lats = num.array(
                [subsource.lat for subsource in subsources], dtype=num.float)
            lons = num.array(
                [subsource.lon for subsource in subsources], dtype=num.float)

            assert num.all(lats == lats[0]) and num.all(lons == lons[0])
            lat, lon = lats[0], lons[0]

            # if not same use:
            # lat, lon = center_latlon(subsources)

            depth = float(num.mean([p.depth for p in subsources]))
            t = float(num.mean([p.time for p in subsources]))
            kwargs.update(time=t, lat=float(lat), lon=float(lon), depth=depth)

        gf.Source.__init__(self, subsources=subsources, **kwargs)

    def get_factor(self):
        return 1.0

    def discretize_basesource(self, store, target=None):

        dsources = []
        t0 = self.subsources[0].time
        for sf in self.subsources:
            #assert t0 == sf.time
            ds = sf.discretize_basesource(store, target)
            ds.m6s *= sf.get_factor()
            dsources.append(ds)

        return gf.DiscretizedMTSource.combine(dsources)



class MultiRectangularProblem(Problem):

    nsources = 2
    problem_parameters = []
    problem_waveform_parameters = []

    for i in range(nsources):
        problem_parameters.append(Parameter('north_shift%s' % i, 'm', label='Northing', **as_km))
        problem_parameters.append(Parameter('east_shift%s' % i, 'm', label='Easting', **as_km))
        problem_parameters.append(Parameter('depth%s' % i, 'm', label='Depth', **as_km))
        problem_parameters.append(Parameter('length%s' % i, 'm', label='Length', **as_km))
        problem_parameters.append(Parameter('width%s' % i, 'm', label='Width', **as_km))
        problem_parameters.append(Parameter('dip%s' % i, 'deg', label='Dip'))
        problem_parameters.append(Parameter('strike%s' % i, 'deg', label='Strike'))
        problem_parameters.append(Parameter('rake%s' % i, 'deg', label='Rake'))
        problem_parameters.append(Parameter('slip%s' % i, 'm', label='Slip'))


        problem_waveform_parameters.append(Parameter('nucleation_x%s' % i, 'offset', label='Nucleation X'))
        problem_waveform_parameters.append(Parameter('nucleation_y%s' % i, 'offset', label='Nucleation Y'))
        problem_waveform_parameters.append(Parameter('time%s' % i, 's', label='Time'))

    dependants = []
    distance_min = Float.T(default=0.0)

    def pack(self, source):
        arr = self.get_parameter_array(source)
        for ip, p in enumerate(self.parameters):
            if p.name == 'time':
                arr[ip] -= self.base_source.time
        return arr

    def get_source(self, x, i):
        d = self.get_parameter_dict(x[0+9*i:9+i*9])

        p = {}
        for k in self.base_source.keys():
            if k in d:
                p[k] = float(
                    self.ranges[k+str(i)].make_relative(self.base_source[k], d[k]))
        source = self.base_source.clone(**p)
        return source

    def random_uniform(self, xbounds):
        x = num.zeros(self.nparameters)
        for i in range(self.nparameters):
            x[i] = num.random.uniform(xbounds[i, 0], xbounds[i, 1])

        return x

    def preconstrain(self, x):
        # source = self.get_source(x)
        # if any(self.distance_min > source.distance_to(t)
        #        for t in self.targets):
            # raise Forbidden()
        return x

    @classmethod
    def get_plot_classes(cls):
        plots = super(MultiRectangularProblem, cls).get_plot_classes()
        return plots


__all__ = '''
    MultiRectangularProblem
    MultiRectangularProblemConfig
'''.split()
