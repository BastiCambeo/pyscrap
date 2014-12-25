__author__ = 'Sebastian Hofstetter'

import itertools
from idpscraper.models.scraper import http_request
from idpscraper.models.selector import Selector
from idpscraper.models.urlselector import UrlSelector
from idpscraper.models.result import Result
from django.db import models


class Task(models.Model):
    """ A Webscraper Task """

    name = models.TextField(primary_key=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.selectors = list(self.selector_set.all())
        self.url_selectors = list(self.urlselector_set.all())

    @property
    def key_selectors(self):
        """ Returns all key selectors """
        return [selector for selector in self.selectors if selector.is_key]

    @property
    def recursive_url_selectors(self):
        return [url_selector for url_selector in self.urlselector_set.all() if url_selector.has_dynamic_url and url_selector.task_key == self.pk]

    @property
    def results(self):
        return Result.objects.filter(task=self.pk)

    def __str__(self):
        return self.name

    def get_urls(self, results=None, limit=None):
        return itertools.chain(*[url_selector.get_urls(results=results, limit=limit) for url_selector in self.urlselector_set.all()])  # Keep generators intact!

    @staticmethod
    def get(name):
        return Task.objects.get(pk=name)

    def as_table(self, results):
        yield tuple(selector.name for selector in self.selectors)

        for result in results:
            yield tuple(getattr(result, selector.name) if hasattr(result, selector.name) else None for selector in self.selectors)

    def run(self, limit=None, store=True) -> 'list[Result]':
        urls = set(self.get_urls(limit=limit))
        visited_urls = set()
        all_results = []

        while len(urls) > 0:
            url = urls.pop()
            if url not in visited_urls:
                visited_urls.add(url)

                # Fetch Result #
                results = http_request(url, selectors=self.selectors)
                all_results += results

                if store and results:
                    # Store result in database #
                    Result.objects.bulk_create(results)

                    # Schedule new urls on recursive call #
                    if self.recursive_url_selectors:
                        urls.update(self.recursive_url_selectors[0].get_urls(results=results))

        return all_results

    def test(self):
        return self.run(limit=1, store=False)

    def export(self):
        url_selectors = "[%s\n    ]" % ",".join(["""\n      UrlSelector(url="%s", task_key=ndb.%s, selector_name="%s", selector_name2="%s")""" % (url_selector.url, repr(url_selector.task_key), url_selector.selector_name, url_selector.selector_name2) for url_selector in self.url_selectors])

        selectors = "[%s\n    ]" % ",".join(["""\n      Selector(name="%s", is_key=%s, xpath='''%s''', type=%s, regex="%s")""" % (selector.name, selector.is_key, selector.xpath, Selector.TYPE_REAL_STR[selector.type], selector.regex.replace("\\", "\\\\")) for selector in self.selectors])

        return """Task(
    name="%s",
    url_selectors=%s,
    selectors=%s\n)""" % (self.name, url_selectors, selectors)

    def export_to_excel(self):
        return Task.export_data_to_excel(data=self.as_table(self.results))

    @staticmethod
    def export_data_to_excel(data):
        import xlwt  # Excel export support
        import io  # for files in memory

        w = xlwt.Workbook()
        ws = w.add_sheet("data")

        # write #
        for x, row in enumerate(data):
            for y, column in enumerate(row):
                ws.write(x, y, column)

        # save #
        f = io.BytesIO('%s.xls' % "export")
        w.save(f)
        del w, ws
        f.seek(0)
        return f.read()

    @staticmethod
    def example_tasks() -> 'list[Task]':
        task = Task(name="test")
        task.save()
        Selector(name="spieler_id", type=Selector.INTEGER, xpath="""(//a[@class="megamenu"])[1]/@href""", task=task, is_key=True).save()
        Selector(name="injury", type=Selector.STRING, xpath="""//table[@class="items"]//tr/td[2]/text()""", task=task).save()
        Selector(name="from", type=Selector.DATETIME, xpath="""//table[@class="items"]//tr/td[3]/text()""", task=task, is_key=True).save()
        UrlSelector(url="http://www.transfermarkt.de/spieler/verletzungen/spieler/10", task=task).save()
