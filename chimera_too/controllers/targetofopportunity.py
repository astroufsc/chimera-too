# This is an example of an simple instrument.
import json
import logging
import os
import socket
import threading
import time

import ephem
from chimera.core.chimeraobject import ChimeraObject
from chimera.util.coord import Coord
from chimera.util.position import Position
from gcn.voeventclient import _open_socket, _ingest_packet
from lxml.etree import XMLSyntaxError
from telegram.ext import Updater, CommandHandler

import gcn
import datetime

from chimera_too.util import voevent2html
from chimera_too.util.VOEventLib import VOEvent
from chimera_too.util.astropysics_obstools import get_SFD_dust


class GCNListener(threading.Thread):

    def __init__(self, host="68.169.57.253", port=8099, ivorn="ivo://python_voeventclient/anonymous",
                 iamalive_timeout=150, max_reconnect_timeout=1024, handler=None, log=None):

        threading.Thread.__init__(self)

        self.abort = threading.Event()
        self.abort.clear()
        self.host = host
        self.port = port
        self.ivorn = ivorn
        self.iamalive_timeout = iamalive_timeout
        self.max_reconnect_timeout = max_reconnect_timeout
        self.handler = handler
        self.log = log

    def stop(self):
        self.abort.set()

    def run(self):
        # todo: self.log.debug("run...")
        self.listen(self.host, self.port, self.ivorn, self.iamalive_timeout, self.max_reconnect_timeout, self.handler,
                    self.log)

    def listen(self, host, port, ivorn, iamalive_timeout, max_reconnect_timeout, handler, log):
        """
        This was copied from pygcn to implement a it with async support

        Connect to a VOEvent Transport Protocol server on the given `host` and
        `port`, then listen for VOEvents until interrupted (i.e., by a keyboard
        interrupt, `SIGINTR`, or `SIGTERM`).

        In response packets, this client is identified by `ivorn`.

        If `iamalive_timeout` seconds elapse without any packets from the server,
        it is assumed that the connection has been dropped; the client closes the
        connection and attempts to re-open it, retrying with an exponential backoff
        up to a maximum timeout of `max_reconnect_timeout` seconds.

        If `handler` is provided, it should be a callable that takes two arguments,
        the raw VOEvent payload and the ElementTree root object of the XML
        document. The `handler` callable will be invoked once for each incoming
        VOEvent. See also `gcn.handlers` for some example handlers.

        If `log` is provided, it should be an instance of `logging.Logger` and is
        used for reporting the client's status. If `log` is not provided, a default
        logger will be used.

        Note that this function does not return."""
        if log is None:
            log = logging.getLogger('gcn.listen')

        while True:
            sock = _open_socket(host, port, iamalive_timeout, max_reconnect_timeout, log)

            if self.abort.is_set():
                break

            try:
                while True:
                    if self.abort.is_set():
                        break
                    _ingest_packet(sock, ivorn, handler, log)
            except socket.timeout:
                log.warn("timed out")
            except socket.error:
                log.exception("socket error")
            except XMLSyntaxError:
                log.warn("XML syntax error")
            finally:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except socket.error:
                    log.exception("could not shut down socket")

                try:
                    sock.close()
                except socket.error:
                    log.exception("could not close socket")
                else:
                    log.info("closed socket")


class GCNHandlers(object):

    def __init__(self, events_dir=None, www_dir=None, log=None):
        self.events_dir = events_dir
        self.www_dir = www_dir
        # self.logger = log
        self.log = log

    # def log(self, *args, **kwargs):
    #     if self.logger is not None:
    #         return self.logger(*args, **kwargs)


class TargetOfOpportunity(ChimeraObject):
    __config__ = {
        # chimera:
        "telescope": "/Telescope/0",
        "camera": "/Camera/0",
        "filterwheel": "/FilterWheel/0",

        # GCN:
        "gcn-server": "68.169.57.253:8099",
        "gcn-events_dir": "~/data/gcn_test/",
        "gcn-www": "http://localhost/",

        # Observability:
        "obs-packets": range(1000),  # [60, 61, 62, 63, 64, 65, 67, 120, 121, 127, 128, 53, 54, 55],
        "obs-min_alt": -999,
        "obs-ebv_max": 999,
        "obs-min_moondist": 10,
        "obs-sequence": "~/.chimera/grb_sequence.json",

        # Telegram
        "telegram-token": None,
    }

    def __init__(self):
        ChimeraObject.__init__(self)
        self.target = None
        self.last_update = datetime.datetime.now()

    def __start__(self):
        # self.doSomething("test argument")

        self._gcn = None
        self._Handlers = GCNHandlers(self["gcn-events_dir"], self["gcn-www"])
        self.listen()
        self.dust_file = str(os.path.dirname(__file__) + '/../data/SFD_dust_1024_%s.fits')
        self.abort = threading.Event()
        self.abort.clear()

        # if self["telegram-token"] is not None:
        #     self.telegram_updater = Updater(self["telegram-token"])
        #     self.telegram_updater.dispatcher.add_handler(CommandHandler('set', self.telegram_set_target, pass_args=True,
        #                                                                 pass_job_queue=True,
        #                                                                 pass_chat_data=True))
        #     self.telegram_updater.dispatcher.add_handler(CommandHandler('point', self.telegram_point_target))
        #     self.telegram_updater.start_polling()
        #     self.telegram_updater.idle()

        return True

    def __stop__(self):
        self._gcn.stop()
        self._gcn.join()

    def getSite(self):
        return self.getManager().getProxy("/Site/0")

    def getTelescope(self):
        return self.getManager().getProxy(self["telescope"])

    def getCamera(self):
        return self.getManager().getProxy(self["camera"])

    def getFilterWheel(self):
        return self.getManager().getProxy(self["filterwheel"])

    ##### HANDLERS #####
    def archive(self, payload, root):
        """Payload handler that archives VOEvent messages as files in the current
        working directory. The filename is a URL-escaped version of the messages'
        IVORN."""
        if self['gcn-events_dir'] is None or self['gcn-www'] is None:
            return None
        ivorn = root.attrib['ivorn']
        event_file = ivorn.strip('ivo://nasa.gsfc.gcn/')
        filename_raw = "%s/raw/%s.xml" % (os.path.expanduser(self['gcn-events_dir']), event_file)
        filename_html = "%s/html/%s.html" % (os.path.expanduser(self['gcn-events_dir']), event_file)
        html = voevent2html.format_to_string(VOEvent.parseString(payload))
        with open(filename_html, "w") as f:
            f.write(html)
        with open(filename_raw, "w") as f:
            f.write(payload)
        if self.log is not None:
            self.log.info("archived %s", ivorn)
        return '%s/html/%s.html' % (self['gcn-www'], event_file), html

    def chimera_handler(self, payload, root):
        t0 = time.time()
        # Check if it is a real GRB
        ra, dec = float(
            root.find(
                "./WhereWhen/ObsDataLocation/ObservationLocation/AstroCoords/Position2D/Value2/C1").text), float(
            root.find("./WhereWhen/ObsDataLocation/ObservationLocation/AstroCoords/Position2D/Value2/C2").text)
        packet_type = int(root.find("./What/Param[@name='Packet_Type']").attrib['value'])

        site = self.getSite()
        ephem_site = site.getEphemSite(site.ut())
        grb = ephem.FixedBody()
        grb._ra, grb._dec = ra, dec
        grb.compute(ephem_site)
        # Conditions to pull the observation trigger
        # TODO: implement min_moon_distance -> Position(coord.fromD(grb.alt), coord.fromD(grb.az)) - site.moonpos()
        # In[8]: a = Position.fromAltAz(Coord.fromD(10), Coord.fromD(10))
        #
        # In[9]: b = Position.fromAltAz(Coord.fromD(10), Coord.fromD(20))
        #
        # In[11]: a.angsep(b).D
        # Out[11]: 10.0
        moondist = Position.fromAltAz(Coord.fromD(float(grb.alt)), Coord.fromD(float(grb.az))).angsep(site.moonpos())
        if moondist > self['obs-min_moondist']:
            self.log.debug("Moon is OK! Moon distance = %.2f deg" % moondist)
        else:
            self.log.debug("Moon is NOT OK! Moon distance = %.2f deg" % moondist)

        # TODO: check if Test_Notice != True (for INTEGRAL)
        if grb.alt >= self['obs-min_alt'] and packet_type in range(1000):  # self['obs-packets']:
            gal_coord = ephem.Galactic(grb)
            ebv = get_SFD_dust([gal_coord.long], [gal_coord.lat], dustmap=self.dust_file, interpolate=False)
            if ebv < self['obs-ebv_max']:
                self.log.debug('Total analysis time: %6.3f secs' % (time.time() - t0))
                self.trigger_observation(ra, dec)
        else:
            self.log.debug("Reject alert type %i. ALT = %.2f, RA = %.2f DEC = %.2f. Config: %d, %s" % (
                packet_type, grb.alt, ra, dec, self['obs-min_alt'], str(self['obs-packets'])))

    def acquire_telescope(self):
        """
        Acquires telescope green light to start observations
        :return:
        """
        # TODO: this should be some sort of supervisor action
        # todo: set ToO flag from CLOSE to READY, wake supervisor, then wait for OPERATING

    def release_telescope(self):
        """
        Releases telescope back to normal activities
        :return:
        """
        # TODO: this should be some sort of supervisor action
        # TODO: set ToO flag to CLOSE, releasing the telescope. Wake supervisor after it.

    def trigger_observation(self, ra, dec, trigger_time=datetime.datetime.utcnow()):
        """
        Acquire observatory control, point and start exposing
        :return:
        """

        # Clear previous abort state
        self.abort.clear()

        # Acquire telescope via supervisor action
        self.acquire_telescope()
        telescope = self.getTelescope()

        # Point
        self.log.debug("Slewing to ra, dec %.2f %.2f" % (ra, dec))
        telescope.slewToRaDec(Position.fromRaDec(Coord.fromD(ra), Coord.fromD(dec)))

        # Start expose sequence
        # TODO: register a method change_filter to the camera readout
        camera = self.getCamera()
        filterwheel = self.getFilterWheel()
        with open(os.path.expanduser("~/.chimera/grb_sequence.json")) as fp:
            sequence = json.load(fp)
        for request in sequence:
            self.log.debug("Exposing: %s" % str(request))
            filterwheel.setFilter(request.pop('filter'))
            camera.expose(request)
            if self.abort.is_set():
                self.release_telescope()
                return False

        self.release_telescope()
        return True

    def update_observation(self, update_time=datetime.datetime.utcnow()):
        """
        Called to update coordinates after trigger
        :return:
        """

    def abort_trigger(self):
        self.abort.set()

    # def telegram_handler(self, payload, root):
    #     msg = 'GRB ALERT - %s - ra: %3.2f, dec: %3.2f, alt: %i deg, E_BV: %3.2f - %s' % (
    #         get_notice_types_dict()[packet_type],
    #         ra, dec, int(grb.alt * 57.2957795),
    #         ebv, link)
    #     for chat_id in configuration["telegram_chat_ids"]:
    #         send_telegram_message(configuration['telegram_token'], chat_id, msg)

    # def email_handler(self, payload, root):
    #     for to in configuration['to_emails'].split(','):
    #         send_html_email(configuration['from_email'], to, 'GRB ALERT', html,
    #                         configuration['smtp_server'],
    #                         use_tls=configuration['smtp_usetls'] == "True",
    #                         username=configuration['smtp_user'],
    #                         password=configuration['smtp_password'])

    ##### HANDLERS #####

    def gcn_handler(self, payload, root):
        # Run chimera observational decision algorithm
        self.chimera_handler(payload, root)
        # Save to a file
        self.archive(payload, root)
        print root.attrib['ivorn']
        # TODO: telegram
        # TODO: email

    def listen(self):
        host, port = self["gcn-server"].split(":")
        port = int(port)
        self._gcn = GCNListener(host, port, handler=self.gcn_handler, log=self.log)
        self._gcn.start()

    def telegram_set_target(self, bot, update, args, job_queue, chat_data):
        if len(args) != 2:
            update.message.reply_text("Usage: /set HH:MM:SS.S DD:MM:SS.S or /set ra dec (J2000)")
        else:
            self.last_update = datetime.datetime.now()
            ra = Coord.fromHMS(args[0]) if ":" in args[0] else Coord.fromD(float(args[0]))
            dec = Coord.fromDMS(args[1]) if ":" in args[1] else Coord.fromD(float(args[1]))
            self.target = Position.fromRaDec(ra, dec)
            site = self.getSite()
            lst = site.LST_inRads()
            alt = float(site.raDecToAltAz(self.target, lst).alt)
            # TODO: reject if alt< telescope_min_alt!
            moonPos = site.moonpos()
            moonRaDec = site.altAzToRaDec(moonPos, lst)
            moonDist = self.target.angsep(moonRaDec)
            update.message.reply_text(
                'Hello {} arg is {} {}. Object alt = {}, Moon dist = {}'.format(update.message.from_user.first_name,
                                                                                args[0], args[1], alt, moonDist))

    def telegram_point_target(self, bot, update):
        if self.target is not None and datetime.datetime.now() - self.last_update <= datetime.timedelta(seconds=60):
            update.message.reply_text("Pointing to target!")
        else:
            update.message.reply_text("NOT Pointing to target!")


if __name__ == '__main__':
    c = TargetOfOpportunity()
    c.__start__()
