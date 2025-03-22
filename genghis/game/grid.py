import random

#
# . = passable
# # = mountain
# @[number] (e.g. @40) = city
# _ = swamp
# A1 first general on team 1, B2 second on team 2
# etc
class GridMaker:
    def __init__(self, minimum_size, maximum_size, density=None, general_positions=None, players=2):
        self.minimum_size = minimum_size
        self.maximum_size = maximum_size
        self.density = density
        self.general_positions = general_positions
        self.players = players

    def generate(self):
        height = random.randint(self.minimum_size[0], self.maximum_size[0])
        width = random.randint(self.minimum_size[1], self.maximum_size[1])
        dimensions = (height, width)
        total_tiles = height * width

