import logging
import numpy as num
from pyrocko.model import gnss

from pyrocko.plot import automap
from grond.plot.config import PlotConfig
from grond.plot.collection import PlotItem
from grond.problems import CMTProblem, RectangularProblem

import copy
from pyrocko.guts import Tuple, Float, Bool

guts_prefix = 'grond'
km = 1e3

logger = logging.getLogger('grond.targets.gnss_campaign.plot')


class GNSSTargetMisfitPlot(PlotConfig):
    ''' Maps showing surface displacements of GNSS campaigns and the model '''

    name = 'fits_gnss'

    size_cm = Tuple.T(
        2, Float.T(),
        default=(30., 30.),
        help='width and length of the figure in cm')
    show_topo = Bool.T(
        default=True,
        help='show topography')
    show_grid = Bool.T(
        default=True,
        help='show the lat/lon grid')
    show_rivers = Bool.T(
        default=True,
        help='show rivers on the map')
    radius = Float.T(
        optional=True,
        help='radius of the map around campaign center lat/lon')

    def make(self, environ):
        cm = environ.get_plot_collection_manager()
        history = environ.get_history()
        optimiser = environ.get_optimiser()
        ds = environ.get_dataset()

        environ.setup_modelling()

        cm.create_group_automap(
            self,
            self.draw_gnss_fits(ds, history, optimiser),
            title='Static GNSS Surface Displacements',
            section='results',
            feather_icon='map',
            description='Maps showing surface displacements of'
                        ' GNSS campaigns and the mode.')

    def draw_gnss_fits(self, ds, history, optimiser):
        problem = history.problem

        gnss_targets = problem.gnss_targets
        for target in gnss_targets:
            target.set_dataset(ds)

        gms = problem.combine_misfits(history.misfits)
        isort = num.argsort(gms)
        gms = gms[isort]
        models = history.models[isort, :]
        xbest = models[0, :]

        source1 = problem.get_source(xbest, 0)
        source2 = problem.get_source(xbest, 1)
        results = problem.evaluate(
            xbest, result_mode='full', targets=gnss_targets)

        for itarget, (gnss_target, result) in enumerate(
                zip(problem.gnss_targets, results)):
            camp = gnss_target.campaign
            item = PlotItem(
                name='fig_%i' % itarget,
                attributes={
                    'targets': gnss_target.path
                },
                title='Static GNSS Surface Displacements - Campaign %s'
                      % camp.name,
                description='Static surface displacement from GNSS campaign %s'
                            ' (black vectors) and displacements derived from'
                            ' best rupture model (red).' % camp.name)

            lat, lon = camp.get_center_latlon()

            if self.radius is None:
                radius = camp.get_radius()

            if radius == 0.:
                logger.warn('Radius of GNSS campaign %s too small, defaulting\
                to 30 km' % camp.name)
                radius = 30*km

            model_camp = gnss.GNSSCampaign(
                stations=copy.deepcopy(camp.stations),
                name='grond model')
            for ista, sta in enumerate(model_camp.stations):
                sta.north.shift = result.statics_syn['displacement.n'][ista]
                sta.north.sigma = 0.

                sta.east.shift = result.statics_syn['displacement.e'][ista]
                sta.east.sigma = 0.

                sta.up.shift = -result.statics_syn['displacement.d'][ista]
                sta.up.sigma = 0.

            m = automap.Map(
                width=self.size_cm[0],
                height=self.size_cm[1],
                lat=lat,
                lon=lon,
                radius=radius,
                show_topo=self.show_topo,
                show_grid=self.show_grid,
                show_rivers=self.show_rivers,
                color_wet=(216, 242, 254),
                color_dry=(238, 236, 230))

            m.add_gnss_campaign(camp, psxy_style={
                'G': 'black',
                'W': '0.5p,black',
                })

            m.add_gnss_campaign(model_camp, psxy_style={
                'G': 'red',
                'W': '0.5p,red',
                't': 30,
                },
                labels=False)

            if isinstance(problem, CMTProblem):
                from pyrocko import moment_tensor
                from pyrocko.plot import gmtpy

                event = source.pyrocko_event()
                mt = event.moment_tensor.m_up_south_east()

                xx = num.trace(mt) / 3.
                mc = num.matrix([[xx, 0., 0.], [0., xx, 0.], [0., 0., xx]])
                mc = mt - mc
                mc = mc / event.moment_tensor.scalar_moment() * \
                    moment_tensor.magnitude_to_moment(5.0)
                m6 = tuple(moment_tensor.to6(mc))
                symbol_size = 20.
                m.gmt.psmeca(
                    S='%s%g' % ('d', symbol_size / gmtpy.cm),
                    in_rows=[(source.lon, source.lat, 10) + m6 + (1, 0, 0)],
                    M=True,
                    *m.jxyr)

            elif isinstance(problem, RectangularProblem):
                m.gmt.psxy(
                    in_rows=source1.outline(cs='lonlat'),
                    L='+p2p,black',
                    W='1p,black',
                    G='black',
                    t=60,
                    *m.jxyr)
                m.gmt.psxy(
                    in_rows=source2.outline(cs='lonlat'),
                    L='+p2p,black',
                    W='1p,black',
                    G='black',
                    t=60,
                    *m.jxyr)

            yield (item, m)


def get_plot_classes():
    return [GNSSTargetMisfitPlot]
