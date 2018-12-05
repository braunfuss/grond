from pyrocko.guts import Object, Float, Int, List, Tuple, String, load

from grond.meta import GrondError

guts_prefix = 'grond'


inch = 2.54


class PlotFormat(Object):

    @property
    def extension(self):
        return self.name

    def get_dpi(self, size_cm):
        return None

    def render_mpl(self, fig, path, **kwargs):
        raise NotImplementedError

    def render_automap(self, automap, path, **kwargs):
        raise NotImplementedError


class PNG(PlotFormat):
    name = 'pdf'

    dpi = Int.T(
        default=150,
        help='DPI of the figure')

    def get_dpi(self, size_cm):
        return self.dpi

    def render_mpl(self, fig, path, **kwargs):
        return fig.savefig(path, format=self.name, **kwargs)

    def render_automap(self, automap, path, **kwargs):
        return automap.save(path, **kwargs)

class PDF(PlotFormat):
    name = 'pdf'

    dpi = Int.T(
        default=150,
        help='DPI of the figure')

    def get_dpi(self, size_cm):
        return self.dpi

    def render_mpl(self, fig, path, **kwargs):
        return fig.savefig(path, format=self.name, **kwargs)

    def render_automap(self, automap, path, **kwargs):
        return automap.save(path, **kwargs)


class HTML(PlotFormat):
    name = 'html'

    @property
    def extension(self):
        return 'html'

    def render_mpl(self, fig, path, **kwargs):
        import mpld3
        kwargs.pop('dpi')

        mpld3.save_html(
            fig,
            fileobj=path,
            **kwargs)


class PlotConfig(Object):
    name = 'undefined'
    variant = String.T(
        default='default',
        help='Variant of the plot (if applicable)')
    formats = List.T(
        PlotFormat.T(),
        default=[PNG()],
        help='Format of the plot')
    size_cm = Tuple.T(
        2, Float.T(),
        help='size of the plot')
    font_size = Float.T(
        default=10.,
        help='font size')

    @property
    def size_inch(self):
        return self.size_cm[0]/inch, self.size_cm[1]/inch

    def make(self, environ):
        pass


class PlotConfigCollection(Object):
    plot_configs = List.T(PlotConfig.T())

    @classmethod
    def load(cls, path):
        collection = load(filename=path)
        if not isinstance(collection, PlotConfigCollection):
            raise GrondError(
                'invalid plot collection configuration in file "%s"' % path)

        return collection


__all__ = [
    'PlotFormat',
    'PNG',
    'PDF',
    'PlotConfig',
    'PlotConfigCollection',
]
