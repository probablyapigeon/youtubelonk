"""Connected-map checks against room topology and live ownership."""
import copy
import unittest
from types import SimpleNamespace

from lonk_map import _layout, render_map
from lonk_visuals import body_for, display_width


def society():
    names = ['Moss', 'Pit', 'Rock', 'Bush', 'Clearing', 'Meadow']
    rooms = {name: {'level': 0, 'density_ticks': 0, 'dropped': []} for name in names}
    edges = {name: [names[(i-1) % 6], names[(i+1) % 6]] for i, name in enumerate(names)}
    world = SimpleNamespace(tick=7, lonks=[SimpleNamespace(name='Grorp', semantic_id='grorp',
        alive=True, territory='Moss', items=[{'name': 'Crystal Shard'}]),
        SimpleNamespace(name='Krip', semantic_id='krip', alive=True, territory='Pit', items=[])])
    return SimpleNamespace(world=world, rooms=rooms, edges=edges, schools={},
                           settings={'settlement_ticks': 5, 'city_ticks': 10})


class ConnectedMapTests(unittest.TestCase):
    def assert_routes(self, c, width):
        _, _, cards, _, routes, _ = _layout(c, width)
        expected = {tuple(sorted((a, b))) for a, links in c.edges.items() for b in links if a != b}
        self.assertEqual({(a, b) for a, b, _ in routes}, expected)
        for first, second, path in routes:
            for name, cell in ((first, path[0]), (second, path[-1])):
                x, y, w, h = cards[name]
                self.assertTrue(x <= cell[0] < x+w and y <= cell[1] < y+h)
                self.assertTrue(cell[0] in (x, x+w-1) or cell[1] in (y, y+h-1))
            for cell, nxt in zip(path, path[1:]):
                self.assertEqual(abs(cell[0]-nxt[0])+abs(cell[1]-nxt[1]), 1)
            for px, py in path[1:-1]:
                for x, y, w, h in cards.values():
                    self.assertFalse(x <= px < x+w and y <= py < y+h, 'A trail ran through a room')

    def test_draws_real_ring_and_annex_edges(self):
        c = society()
        c.rooms['Bee Annex'] = {'parent': 'Moss', 'level': 0, 'dropped': []}
        c.edges['Moss'].append('Bee Annex')
        c.edges['Bee Annex'] = ['Moss']
        for width in (40, 60, 80, 120):
            with self.subTest(width=width):
                self.assert_routes(c, width)
                output = render_map(c, width)
                self.assertIn('ANNEX: Bee Annex', output)
                self.assertIn('_', output)
                self.assertTrue(all(display_width(line) <= width for line in output.splitlines()[3:]))

    def test_shows_real_inventory_and_ground_without_changing_state(self):
        c = society()
        c.rooms['Moss']['dropped'] = [{'name': 'Golden Acorn'}]
        before = copy.deepcopy(c)
        output = render_map(c, 120)
        self.assertIn(body_for(c.world.lonks[0])+' Grorp', output)
        self.assertIn('Carrying: 💎 Crystal Shard', output)
        self.assertIn('Ground: 🌰 Golden Acorn', output)
        self.assertEqual(c, before)
        c.world.lonks[0].items.clear()
        c.world.lonks[1].items.append({'name': 'Crystal Shard'})
        c.world.lonks[0].territory = 'Bush'
        _, _, _, bodies, _, _ = _layout(c, 120)
        self.assertNotIn('Crystal Shard', '\n'.join(bodies['Moss']))
        self.assertIn('Crystal Shard', '\n'.join(bodies['Pit']))
        self.assertIn('Grorp', '\n'.join(bodies['Bush']))

    def test_disconnected_rooms_do_not_gain_invented_roads(self):
        c = society()
        c.edges = {name: [] for name in c.rooms}
        self.assertEqual(_layout(c, 80)[4], [])
        self.assertIn('Paths: (none)', render_map(c, 80))

    def test_crowded_room_long_items_emoji_and_empty_world_fit(self):
        c = society()
        for i in range(20):
            c.world.lonks.append(SimpleNamespace(name=f'Grorp{i}', alive=True, territory='Moss',
                items=[{'name': '🧑🏽‍🚀' + 'Extraordinary' * 8}]))
        self.assert_routes(c, 80)
        self.assertTrue(all(display_width(line) <= 80 for line in render_map(c, 80).splitlines()[3:]))
        c.rooms, c.edges, c.world.lonks = {}, {}, []
        self.assertIn('0 living Lonks', render_map(c, 80))


if __name__ == '__main__':
    unittest.main()
