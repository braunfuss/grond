import math
import logging

import numpy as num

from pyrocko import gf, moment_tensor as mtm, util
from pyrocko.guts import Float, String, Dict, List, Int, StringChoice
from grond import core

guts_prefix = 'grond'


logger = logging.getLogger('grond.cmt')

km = 1000.

as_km = dict(scale_factor=km, scale_unit='km')


class CMTProblem(core.Problem):

    parameters = [
        core.Parameter('time', 's'),
        core.Parameter('north_shift', 'm', **as_km),
        core.Parameter('east_shift', 'm', **as_km),
        core.Parameter('depth', 'm', **as_km),
        core.Parameter('magnitude'),
        core.Parameter('rmnn'),
        core.Parameter('rmee'),
        core.Parameter('rmdd'),
        core.Parameter('rmne'),
        core.Parameter('rmnd'),
        core.Parameter('rmed'),
        core.Parameter('duration')]

    dependants = [
        core.Parameter('rel_moment_iso'),
        core.Parameter('rel_moment_clvd')]

    base_source = gf.Source.T()
    targets = List.T(core.MisfitTarget.T())

    ranges = Dict.T(String.T(), gf.Range.T())
    distance_min = Float.T(default=0.0)
    nbootstrap = Int.T(default=10)
    mt_type = StringChoice.T(choices=['full', 'deviatoric'])

    def unpack(self, x):
        d = self.parameter_dict(x)
        rm6 = num.array([d.rmnn, d.rmee, d.rmdd, d.rmne, d.rmnd, d.rmed],
                        dtype=num.float)

        m0 = mtm.magnitude_to_moment(d.magnitude)
        m6 = rm6 * m0

        p = {}
        for k in self.base_source.keys():
            if k in d:
                p[k] = float(
                    self.ranges[k].make_relative(self.base_source[k], d[k]))

        stf = gf.HalfSinusoidSTF(duration=float(d.duration))

        source = self.base_source.clone(m6=m6, stf=stf, **p)
        return source

    def make_dependant(self, xs, pname):
        if xs.ndim == 1:
            return self.make_dependant(xs[num.newaxis, :], pname)[0]

        if pname in ('rel_moment_iso', 'rel_moment_clvd'):
            y = num.zeros(xs.shape[0])
            for i, x in enumerate(xs):
                source = self.unpack(x)
                mt = source.pyrocko_moment_tensor()
                res = mt.standard_decomposition()

                if pname == 'rel_moment_iso':
                    ratio_iso, m_iso = res[0][1:3]
                    y[i] = ratio_iso * num.sign(m_iso[0, 0])
                else:
                    ratio_clvd, m_clvd = res[2][1:3]
                    evals, evecs = mtm.eigh_check(m_clvd)
                    ii = num.argmax(num.abs(evals))
                    y[i] = ratio_clvd * num.sign(evals[ii])

            return y

        else:
            raise KeyError(pname)

    def extract(self, xs, i):
        if xs.ndim == 1:
            return self.extract(xs[num.newaxis, :], i)[0]

        if i < self.nparameters:
            return xs[:, i]
        else:
            return self.make_dependant(
                xs, self.dependants[i-self.nparameters].name)

    def pack(self, source):
        m6 = source.m6
        mt = source.pyrocko_moment_tensor()
        rm6 = m6 / mt.scalar_moment()

        x = num.array([
            source.time,
            source.north_shift,
            source.east_shift,
            source.depth,
            mt.moment_magnitude(),
            ] + rm6.tolist() + [source.stf.duration], dtype=num.float)

        return x

    def preconstrain(self, x):

        d = self.parameter_dict(x)
        m6 = num.array([d.rmnn, d.rmee, d.rmdd, d.rmne, d.rmnd, d.rmed],
                       dtype=num.float)

        m9 = mtm.symmat6(*m6)
        if self.mt_type == 'deviatoric':
            trace_m = num.trace(m9)
            m_iso = num.diag([trace_m / 3., trace_m / 3., trace_m / 3.])
            m9 -= m_iso

        m0_unscaled = math.sqrt(num.sum(m9.A**2)) / math.sqrt(2.)

        m9 /= m0_unscaled
        m6 = mtm.to6(m9)
        d.rmnn, d.rmee, d.rmdd, d.rmne, d.rmnd, d.rmed = m6
        x = self.parameter_array(d)

        source = self.unpack(x)
        if any(self.distance_min > source.distance_to(t)
               for t in self.targets):
            raise core.Forbidden()

        return x

    def bounds(self):
        out = []
        for p in self.parameters:
            r = self.ranges[p.name]
            out.append((r.start, r.stop))

        return out

    def dependant_bounds(self):
        out = [
            (-1., 1.),
            (-1., 1.)]

        return out

    def evaluate(self, x, return_traces=False):
        source = self.unpack(x)
        engine = gf.get_engine()
        for target in self.targets:
            target.set_return_traces(return_traces)

        resp = engine.process(source, self.targets)
        data = []
        results = []
        for source, target, result in resp.iter_results('results'):
            if isinstance(result, gf.SeismosizerError):
                logger.debug(
                    '%s.%s.%s.%s: %s' % (target.codes + (str(result),)))

                data.append((None, None))
                if return_traces:
                    results.append(None)
            else:
                data.append((result.misfit_value, result.misfit_norm))
                if return_traces:
                    results.append(result)

        ms, ns = num.array(data, dtype=num.float).T
        if return_traces:
            return ms, ns, results
        else:
            return ms, ns

    def forward(self, x):
        source = self.unpack(x)
        engine = gf.get_engine()
        plain_targets = [target.get_plain_target() for target in self.targets]

        resp = engine.process(source, plain_targets)
        results = []
        for source, target, result in resp.iter_results('results'):
            if isinstance(result, gf.SeismosizerError):
                logger.debug(
                    '%s.%s.%s.%s: %s' % (target.codes + (str(result),)))

                results.append(None)
            else:
                results.append(result)

        return results

    def get_target_weights(self):
        if self._target_weights is None:
            self._target_weights = num.array(
                [target.get_combined_weight(
                    apply_balancing_weights=self.apply_balancing_weights)
                 for target in self.targets], dtype=num.float)

        return self._target_weights

    def bootstrap_misfit(self, ms, ns, ibootstrap=None):
        w = self.get_bootstrap_weights(ibootstrap) * self.get_target_weights()
        if ibootstrap is None:
            return num.sqrt(
                num.nansum((w*ms[num.newaxis, :])**2, axis=1) /
                num.nansum((w*ns[num.newaxis, :])**2, axis=1))
        else:
            return num.sqrt(num.nansum((w*ms)**2) / num.nansum((w*ns)**2))

    def bootstrap_misfits(self, misfits, ibootstrap):
        w = self.get_bootstrap_weights(ibootstrap)[num.newaxis, :] * \
            self.get_target_weights()[num.newaxis, :]

        bms = num.sqrt(num.nansum((w*misfits[:, :, 0])**2, axis=1) /
                       num.nansum((w*misfits[:, :, 1])**2, axis=1))
        return bms

    def global_misfit(self, ms, ns):
        ws = self.get_target_weights()
        m = num.sqrt(num.nansum((ws*ms)**2) / num.nansum((ws*ns)**2))
        return m

    def global_misfits(self, misfits):
        ws = self.get_target_weights()[num.newaxis, :]
        gms = num.sqrt(num.nansum((ws*misfits[:, :, 0])**2, axis=1) /
                       num.nansum((ws*misfits[:, :, 1])**2, axis=1))
        return gms

    def global_contributions(self, misfits):
        ws = self.get_target_weights()[num.newaxis, :]
        gcms = (ws*misfits[:, :, 0])**2 / \
            num.nansum((ws*misfits[:, :, 1])**2, axis=1)[:, num.newaxis]

        return gcms


class CMTProblemConfig(core.ProblemConfig):

    ranges = Dict.T(String.T(), gf.Range.T())
    distance_min = Float.T(default=0.0)
    nbootstrap = Int.T(default=10)
    mt_type = StringChoice.T(choices=['full', 'deviatoric'])

    def get_problem(self, event, targets):
        if event.depth is None:
            event.depth = 0.

        base_source = gf.MTSource.from_pyrocko_event(event)
        base_source.stf = gf.HalfSinusoidSTF(duration=1.0)

        subs = dict(
            event_name=event.name,
            event_time=util.time_to_str(event.time))

        problem = CMTProblem(
            name=self.name_template % subs,
            apply_balancing_weights=self.apply_balancing_weights,
            base_source=base_source,
            targets=targets,
            ranges=self.ranges,
            distance_min=self.distance_min,
            nbootstrap=self.nbootstrap,
            mt_type=self.mt_type)

        return problem


__all__ = [
    'CMTProblem',
    'CMTProblemConfig',
]