from config import *



class Action(object):
    def can_execute(self, player):
        return True
    
    def is_blocking(self):
        '''Return whether this action should block execution of the game until part of its
        execution is finished. i.e. is another decision required after it?'''
        return False
    
    def execute(self, player):
        raise Exception('Not implented')

class NullAction(Action):
    def execute(self, player):
        pass
    
    def __repr__(self):
        return '(None)'
        
        
class MoveProvostAction(Action):
    def __init__(self, spaces):
        self.spaces = spaces
        
    def can_execute(self, player):
        return 0 < player.game.provost + self.spaces < LAST_SPACE
        
    def execute(self, player):
        player.game.provost += self.spaces
        
    def __repr__(self):
        return 'P%+d' % self.spaces
       
class ProduceAction(Action):
    def __init__(self, **output):
        self.output = output
        
    def execute(self, player):
        player.add_resources(self.output)
        
    def __repr__(self):
        return format_resources(self.output)
        
class TradeAction(Action):
    ''' An action that involves exchanging some amount of resources/money for others.'''
    def __init__(self, input, output={}):
        self.input = input
        self.output = output
        
    def can_execute(self, player):
        return player.has_resources(self.input)
        
    def execute(self, player):
        player.remove_resources(self.input)
        player.add_resources(self.output)
        
    def __repr__(self):
        return '%s->%s' % (format_resources(self.input), format_resources(self.output))
        
class JoustAction(TradeAction):
    def __init__(self):
        TradeAction.__init__(self, input={'cloth':1, 'money':1}, output={})
        
    def execute(self, player):
        player.remove_resources(self.input)
        player.game.award_favor(player)
        
    def is_blocking(self):
        ''' Requires subsequent selection of which favor to take '''
        return True
        
    def __repr__(self):
        return '%s->RF' % format_resources(self.input)
        
class ConstructAction(TradeAction):
    def __init__(self, building, cost):
        self.building = building
        TradeAction.__init__(self, input=cost, output={})
        
    def can_execute(self, player):
        # Prevent double construction of buildings
        return TradeAction.can_execute(self, player) and self.building in (player.game.wood_buildings + player.game.stone_buildings)
        
    def execute(self, player):
        player.remove_resources(self.input)
        if self.building in player.game.wood_buildings:
            player.game.wood_buildings.remove(self.building)
        if self.building in player.game.stone_buildings:
            player.game.stone_buildings.remove(self.building)
        if null_building in player.game.normal_buildings:
            player.game.normal_buildings[player.game.normal_buildings.index(null_building)] = self.building
        else:
            player.game.normal_buildings.append(self.building)
        self.building.owner = player
        self.building.worker = None
        player.points += self.building.points
        
    def __repr__(self):
        return '%s->[%s]' % (format_resources(self.input), self.building)

class CastleAction(TradeAction):
    def __init__(self, res1, res2):
        TradeAction.__init__(self, input={'food':1, res1:1, res2:1}, output={})
        
    def __repr__(self):
        return '%s->Castle' % format_resources(self.input)
        
class LawyerAction(TradeAction):
    def __init__(self, target, discount=False):
        self.target = target
        if discount:
            TradeAction.__init__(self, input={'cloth':1}, output={})
        else:
            TradeAction.__init__(self, input={'cloth':1, 'money':1}, output={})
        
    def execute(self, player):
        player.remove_resources(self.input)
        i = player.game.normal_buildings.index(self.target)
        residence = ResidenceBuilding()
        player.game.normal_buildings[i] = residence
        residence.owner = player
        
    def __repr__(self):
        return '[%s]->Residence' % self.target

class Decision(object):
    pass

class ActionDecision(Decision):
    ''' A decision is a choice between a number of actions '''
    def __init__(self, actions):
        self.actions = actions
        
class WorkerDecision(Decision):
    def __init__(self, buildings):
        self.buildings = buildings
        self.buildings = [None] + self.buildings
        
class FavorTrackDecision(Decision):
    def __init__(self, player):
        self.player = player

class FavorDecision(ActionDecision):
    def __init__(self, player, actions):
        self.player = player
        self.actions = actions

class Building(object):
    ''' A simple building has a static list of actions the player may choose from '''
    def __init__(self, name, *actions):
        self.name = name
        self.actions = actions
        
    def activate(self, player):
        actions = [action for action in self.actions if action.can_execute(player)]
        return ActionDecision(actions)
        #if len(actions) == 0:
        #    return
        #elif len(actions) == 1:
        #    print actions
        #    actions[0].execute(player)
        #else:
        #    print actions
        
    def constructable(self, points, **cost):
        self.cost = cost
        self.points = points
        return self
            
    def __repr__(self):
        return '/'.join([str(action) for action in self.actions if not isinstance(action, NullAction)])
    
class NullBuilding(Building):
    def activate(self, player):
        return ActionDecision(NullAction())
    def __eq__(self, other):
        return isinstance(other, NullBuilding)
        
class ResidenceBuilding(Building):
    def __init__(self):
        self.name = 'Residence'
        
    def __repr__(self):
        return 'Residence'
        
class MarketBuilding(Building):
    ''' A market building allows the sale of any resource for money'''
    def __init__(self, name, amount):
        self.name = name
        self.amount = amount
        self.actions = [TradeAction({resource:1}, {'money':amount}) for resource in RESOURCES]
        self.actions.append(NullAction())
    def __repr__(self):
        return 'R->%d' % self.amount

class PeddlerBuilding(Building):
    ''' A peddler building allows the purchase of any resource for money'''
    def __init__(self, name, amount):
        self.name = name
        self.amount = amount
        self.actions = [TradeAction({'money':amount}, {resource:1}) for resource in RESOURCES if resource != 'gold']
        self.actions.append(NullAction())
    def __repr__(self):
        return '%d->R' % self.amount
    
class GuildBuilding(Building):
    def __init__(self, name):
        self.name = name
        self.actions = [MoveProvostAction(i) for i in [-3, -2, -1, 0, 1, 2, 3]]
    def __repr__(self):
        return 'Prov'
    
class CarpenterBuilding(Building):
    def __init__(self, name, discount=False):
        self.name = name
        self.actions = []
        for building in wood_buildings:
            cost = building.cost.copy()
            if discount:
                del cost['wood']
            if 'any' in cost: # Ugh, have to deal with being able to construct some buildings with anything
                for resource in RESOURCES:
                    new_cost = {}
                    for key, value in cost.items():
                        if key == 'any':
                            new_cost[resource] = new_cost.get(resource,0) + value
                        else:
                            new_cost[key] = new_cost.get(key,0) + value
                    self.actions.append(ConstructAction(building, new_cost))
            else:
                self.actions.append(ConstructAction(building, cost))
        if not discount:
            self.actions.append(NullAction())
    def __repr__(self):
        return 'Carpenter'
    
class MasonBuilding(Building):
    def __init__(self, name, discount=False):
        self.name = name
        self.actions = []
        for building in stone_buildings:
            cost = building.cost.copy()
            if discount:
                del cost['stone']
            self.actions.append(ConstructAction(building, cost))
        if not discount:
            self.actions.append(NullAction())
    def __repr__(self):
        return 'Mason'
    
class LawyerBuilding(Building):
    def __init__(self, name, discount=False):
        self.name = name
        self.discount = discount
    def activate(self, player): # Transformable building must be dynamically found
        buildings = [building for building in player.game.normal_buildings if \
                        (building.owner == None or building.owner == player) and not hasattr(building, 'fixed') \
                        and not isinstance(building, LawyerBuilding) and not isinstance(building, NullBuilding)]
        self.actions = []
        for building in buildings:
            self.actions.append(LawyerAction(building, discount=self.discount))
        self.actions.append(NullAction())
        return Building.activate(self, player) # Let's still take advantage of the superclass filtering
    def __repr__(self):
        return 'Lawyer'
    
class CastleBuilding(Building):
    def __init__(self):
        self.name = 'Castle'
        self.actions = [CastleAction('wood', 'stone'), CastleAction('wood', 'cloth'), CastleAction('cloth', 'stone'),
                        CastleAction('wood', 'gold'), CastleAction('stone', 'gold'), CastleAction('cloth', 'gold'), NullAction()]

    def __repr__(self):
        return 'Castle'
    
     

castle = CastleBuilding()   
trading_post = Building("Trading Post", ProduceAction(money=3))
merchant_guild = GuildBuilding("Merchant's Guild")
joust_field = Building("Joust Field",JoustAction(), NullAction())

stone_tailor = Building("Tailor", TradeAction({'cloth':2}, {'points':4}), TradeAction({'cloth':3},{'points':6}), NullAction()).constructable(6, stone=1, wood=1)
stone_buildings = [stone_tailor]

wood_farm_food = Building("Farm",ProduceAction(food=2), ProduceAction(cloth=1)).constructable(2, wood=1, food=1)
wood_farm_cloth = Building("Farm",ProduceAction(cloth=2), ProduceAction(food=1)).constructable(2, wood=1, food=1)
wood_quarry = Building("Quarry", ProduceAction(stone=2)).constructable(2, wood=1, food=1)
wood_sawmill = Building("Sawmill", ProduceAction(wood=2)).constructable(2, wood=1, food=1)
wood_market = MarketBuilding("Market", 6).constructable(2, wood=1, any=1)
wood_peddler = PeddlerBuilding("Peddler", 1).constructable(2, wood=1, any=1)
wood_mason = MasonBuilding("Mason").constructable(4, wood=1, food=1)
wood_lawyer = LawyerBuilding("Lawyer").constructable(4, wood=1, cloth=1)

wood_buildings = [wood_farm_food, wood_farm_cloth, wood_quarry, wood_sawmill, wood_market, wood_peddler, wood_mason, wood_lawyer]



neutral_farm = Building("Farm",ProduceAction(food=1), ProduceAction(cloth=1))
neutral_forest = Building("Forest",ProduceAction(food=1), ProduceAction(wood=1))
neutral_sawmill = Building("Sawmill", ProduceAction(wood=1))
neutral_quarry = Building("Quarry", ProduceAction(stone=1))
neutral_market = MarketBuilding("Market", 4)
neutral_carpenter = CarpenterBuilding("Carpenter")

fixed_peddler = PeddlerBuilding("Peddler", 2)
fixed_peddler.fixed = True
fixed_carpenter = CarpenterBuilding("Carpenter")
fixed_carpenter.fixed = True
fixed_gold = Building("Gold Mine", ProduceAction(gold=1))
fixed_gold.fixed = True



special_buildings = [castle, trading_post, merchant_guild, joust_field]
neutral_buildings = [neutral_carpenter, neutral_farm, neutral_forest, neutral_sawmill, neutral_quarry, neutral_market]
fixed_buildings = [fixed_peddler, fixed_carpenter]

null_building = NullBuilding("Null")

point_track = [Building(None, ProduceAction(points=p)) for p in range(1, 6)]
money_track = [Building(None, ProduceAction(money=m)) for m in range(3, 8)]
resource_track = [Building(None, ProduceAction(food=1)), Building(None, ProduceAction(wood=1), ProduceAction(stone=1)),
                Building(None, ProduceAction(cloth=1)), Building(None, ProduceAction(wood=1, stone=1, cloth=1)), Building(None, ProduceAction(gold=1))]
building_track = [Building(None, NullAction()), CarpenterBuilding(None, discount=True), MasonBuilding(None, discount=True), LawyerBuilding(None, discount=True)]

favor_tracks = [point_track, money_track, resource_track, building_track]
track_names = ['Points', 'Money', 'Resource', 'Building']

if __name__ == '__main__':
    from player import *
    player = Player(None, None)
    print wood_quarry.activate(player).actions
    #print player
    #print merchant_guild