import copy
import mock
import unittest

from eventsmanager.manager import EventsManager


class TestEventsManager(unittest.TestCase):

    @staticmethod
    def callable_wo_effect(*args, **kwargs):
        pass

    @staticmethod
    def callable_w_error(*args, **kwargs):
        return 1/0

    @classmethod
    def setUpClass(cls):
        # provide all required information for our fake events
        cls.names = ["A", "B", "C"]
        cls.adders = [lambda a: a,
                      lambda b: b,
                      lambda c, d: c + d]
        cls.adders_args = [(5, ),
                           ([5, 5], ),
                           (5, 5)]
        cls.exp_id_list = [[5],
                           [5, 5],
                           [10]]
        cls.owners = ["app {}".format(_) for _ in cls.names]
        cls.descriptions = ["description for {}".format(_) for _ in cls.owners]

        cls.prefilled_events = {}
        for i, name in enumerate(cls.names):
            cls.prefilled_events[name] = {"adder": cls.adders[i],
                                          "adder_args": cls.adders_args[i],
                                          "adder_kwargs": {},
                                          "remover": None,
                                          "remover_args": (),
                                          "remover_kwargs": {},
                                          "paused": False,
                                          "id_list": [],
                                          "owner": cls.owners[i],
                                          "description": cls.descriptions[i]
                                          }

    @classmethod
    def setUp(cls):
        cls.event_patch = copy.deepcopy(cls.prefilled_events)

    def test_add_event(self):
        for i, name in enumerate(self.names):
            EventsManager().add_event(name,
                                      self.adders[i],
                                      adder_args=self.adders_args[i],
                                      owner=self.owners[i],
                                      description=self.descriptions[i])
            # check if there is the eventname entry
            self.assertIn(name, EventsManager().data,
                          msg="Missing event entry for {}".format(name)
                          )
            # check if the event is unpaused by default
            self.assertFalse(EventsManager().data[name]["paused"],
                             msg="Expected a fresh '{}' event to be unpaused".format(name)
                             )
            # check if the id_list is a ist containing the returned value of the callable
            self.assertEqual(self.exp_id_list[i], EventsManager().data[name]["id_list"])

            # check if adder info was in inluded correctly
            self.assertEqual(self.adders[i], EventsManager().data[name]["adder"])
            self.assertEqual(self.adders_args[i], EventsManager().data[name]["adder_args"])
            self.assertEqual({}, EventsManager().data[name]["adder_kwargs"])

            # check if owner matches
            self.assertEqual(self.owners[i], EventsManager().data[name]["owner"])

            # check if description matches
            self.assertEqual(self.descriptions[i], EventsManager().data[name]["description"])

        # check if the data looks the same if an adder is not callable
        # or throws an error
        data = EventsManager().data.copy()
        EventsManager().add_event("Z", self.callable_w_error)
        self.assertDictEqual(data, EventsManager().data)

        # check if the event data looks the same if we want to register
        # an event that already exists
        EventsManager().add_event("A", self.callable_wo_effect)
        self.assertDictEqual(data, EventsManager().data)

    def test_attach_remover(self):
        # check if we get a proper assertion error if the given event was not
        # registered
        with mock.patch.object(EventsManager, "data", {1: 2}):
            with self.assertRaises(AssertionError) as e:
                EventsManager().attach_remover("Z", self.callable_wo_effect)
                self.assertIn("No event named", e.exception.message)

        EventsManager().attach_remover("A", self.callable_wo_effect, 5, {"test": True})
        event_a_data = EventsManager().data.get("A")
        assert event_a_data, "Missing data for event named '{}'".format("A")
        self.assertEqual(self.callable_wo_effect, event_a_data["remover"])
        self.assertEqual(5, event_a_data["remover_args"])
        self.assertEqual({"test": True}, event_a_data["remover_kwargs"])

    def test_remove_event(self):
        # expect an assertion error if the event doesn't exist
        with mock.patch.object(EventsManager, "data", self.event_patch):
            with self.assertRaises(AssertionError):
                EventsManager().remove_event("Z")

        # add a remover that throws an error and check if the event stays
        # active
        self.event_patch["A"]["remover"] = self.callable_w_error
        with mock.patch.object(EventsManager, "data", self.event_patch):
            EventsManager().remove_event("A")
            self.assertIn("A", EventsManager().registered_events)

        # remove as soon as this feature has been implemented,
        # so far check for an NotImplementedError
        with mock.patch.object(EventsManager, "data", self.event_patch):
            with self.assertRaises(NotImplementedError):
                EventsManager().remove_event("A", restore_on_fail=True)

        # check for a successful event removal
        self.event_patch["A"]["remover"] = self.callable_wo_effect
        with mock.patch.object(EventsManager, "data", self.event_patch):
            EventsManager().remove_event("A")
            self.assertNotIn("A", EventsManager().registered_events)

    def test_paused_events(self):
        with mock.patch.object(EventsManager, "data", self.event_patch):
            self.assertEqual([], EventsManager().paused_events)

        # set fake event pause state
        self.event_patch["A"]["paused"] = True
        with mock.patch.object(EventsManager, "data", self.event_patch):
            self.assertEqual(["A"], EventsManager().paused_events)

    def test_pause_event(self):
        event_patch = copy.deepcopy(self.prefilled_events)
        event_patch["A"]["remover"] = self.callable_w_error
        with mock.patch.object(EventsManager, "data", event_patch):
            EventsManager().pause_event("A")
            self.assertIn("A", EventsManager().registered_events)

        event_patch["A"]["remover"] = self.callable_wo_effect
        with mock.patch.object(EventsManager, "data", event_patch):
            EventsManager().pause_event("A")
            self.assertIn("A", EventsManager().data)
            self.assertTrue(EventsManager().data["A"]["paused"])

    def test_pause_events(self):
        for event_name, event_data in self.event_patch.iteritems():
            event_data["remover"] = self.callable_wo_effect

        with mock.patch.object(EventsManager, "data", self.event_patch):
            EventsManager().pause_events(exclude=["A"])
            for event_name, event_data in EventsManager().data.iteritems():
                if event_name == "A":
                    self.assertFalse(event_data["paused"])
                else:
                    self.assertTrue(event_data["paused"])

    def test_resume_event(self):
        # it looks like we are hitting a limitation within mock.patch
        # because the patch is not working anymore
        # the data attribute doesn't get any replacement, but still exists
        # we can take this data directly and use the contextmanager only
        # for our temporary actions
        # smells fishy but works
        with mock.patch.object(EventsManager, "", self.event_patch, create=True):
            with self.assertRaises(AssertionError):
                EventsManager().resume_event("A")

            EventsManager().data["A"]["paused"] = True
            EventsManager().resume_event("A")
            self.assertFalse(EventsManager().data["A"]["paused"])
