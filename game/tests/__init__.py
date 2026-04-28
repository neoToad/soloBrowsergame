import random

import factory.random


FACTORY_TEST_SEED = 1337
random.seed(FACTORY_TEST_SEED)
factory.random.reseed_random(FACTORY_TEST_SEED)
