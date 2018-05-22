"""
This example shows the trade-off (pareto frontier) of deficit against cost by altering a reservoir control curve.

Two types of control curve are possible. The first is a monthly control curve containing one value for each
month. The second is a harmonic control curve with cosine terms around a mean. Both Parameter objects
are part of pywr.parameters.

Inspyred is used in this example to perform a multi-objective optimisation using the NSGA-II algorithm. The
script should be run twice (once with --harmonic) to generate results for both types of control curve. Following
this --plot can be used to generate an animation and PNG of the pareto frontier.

"""
import json
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter


def get_model_data(harmonic=True):

    with open('two_reservoir.json') as fh:
        data = json.load(fh)

    if harmonic:
        # Patch the control curve parameter
        data['parameters']['control_curve'] = {
            'type': 'AnnualHarmonicSeries',
            'mean': 0.5,
            'amplitudes': [0.5, 0.0],
            'phases': [0.0, 0.0],
            'mean_upper_bounds': 1.0,
            'amplitude_upper_bounds': 1.0,
            'is_variable': True
        }

    return data


def platypus_main(harmonic=False):
    import platypus
    from pywr.optimisation.platypus import PlatypusWrapper

    wrapper = PlatypusWrapper(get_model_data(harmonic=harmonic))

    with platypus.ProcessPoolEvaluator() as evaluator:
        algorithm = platypus.NSGAII(wrapper.problem, population_size=50, evaluator=evaluator)
        algorithm.run(10000)

    plt.scatter([s.objectives[0] for s in algorithm.result],
                [s.objectives[1] for s in algorithm.result])

    objectives = wrapper.model_objectives
    plt.xlabel(objectives[0].name)
    plt.ylabel(objectives[1].name)
    plt.grid(True)
    title = 'Harmonic Control Curve' if harmonic else 'Monthly Control Curve'
    plt.savefig('{} Example ({}).pdf'.format('platypus', title), format='pdf')
    plt.show()


def pygmo_main(harmonic=False):
    import pygmo as pg
    from pywr.optimisation.pygmo import PygmoWrapper

    def update_archive(pop, archive=None):
        if archive is None:
            combined_f = pop.get_f()
        else:
            combined_f = np.r_[archive, pop.get_f()]
        indices = pg.select_best_N_mo(combined_f, 50)
        new_archive = combined_f[indices, :]
        new_archive = np.unique(new_archive.round(4), axis=0)
        return new_archive

    wrapper = PygmoWrapper(get_model_data(harmonic=harmonic))
    prob = pg.problem(wrapper)
    print(prob)
    algo = pg.algorithm(pg.moead(gen=1))
    #algo = pg.algorithm(pg.nsga2(gen=1))

    pg.mp_island.init_pool(2)
    isl = pg.island(algo=algo, prob=prob, size=50, udi=pg.mp_island())

    ref_point = [216500, 4000]
    pop = isl.get_population()

    print('Evolving!')
    archive = update_archive(pop)
    hv = pg.hypervolume(archive)
    vol = hv.compute(ref_point)
    hvs = [vol, ]
    print('Gen: {:03d}, Hypervolume: {:6.4g}, Archive size: {:d}'.format(0, vol, len(archive)))

    for gen in range(20):
        isl.evolve(1)
        isl.wait_check()

        pop = isl.get_population()
        archive = update_archive(pop, archive)

        hv = pg.hypervolume(archive)
        vol = hv.compute(ref_point)
        print('Gen: {:03d}, Hypervolume: {:6.4g}, Archive size: {:d}'.format(gen+1, vol, len(archive)))
        hvs.append(vol)

    hvs = pd.Series(hvs)

    print('Finished!')

    plt.scatter(archive[:, 0], archive[:, 1])

    objectives = wrapper.model_objectives
    plt.xlabel(objectives[0].name)
    plt.ylabel(objectives[1].name)
    plt.grid(True)
    title = 'Harmonic Control Curve' if harmonic else 'Monthly Control Curve'
    plt.savefig('{} Example ({}).pdf'.format('pygmo', title), format='pdf')

    fig, ax = plt.subplots()
    ax.plot(hvs/1e6, marker='o')
    ax.grid(True)
    ax.set_ylabel('Hypervolume')
    ax.set_xlabel('Generation')
    plt.savefig('{} Example Hypervolume ({}).pdf'.format('pygmo', title), format='pdf')

    plt.show()


def inspyred_main(prng=None, display=False, harmonic=False):
    import inspyred
    from pywr.optimisation.inspyred import InspyredOptimisationWrapper
    from random import Random
    from time import time

    if prng is None:
        prng = Random()
        prng.seed(time())

    script_name = os.path.splitext(os.path.basename(__file__))[0]
    stats_file = open('{}-{}-statistics-file.csv'.format(script_name, 'harmonic' if harmonic else 'monthly'), 'w')
    individuals_file = open('{}-{}-individuals-file.csv'.format(script_name, 'harmonic' if harmonic else 'monthly'), 'w')

    wrapper = InspyredOptimisationWrapper(get_model_data(harmonic=harmonic))

    ea = inspyred.ec.emo.NSGA2(prng)
    #ea.variator = [inspyred.ec.variators.blend_crossover,
    #               inspyred.ec.variators.gaussian_mutation]
    ea.terminator = inspyred.ec.terminators.generation_termination
    ea.observer = [
        inspyred.ec.observers.file_observer,
    ]
    final_pop = ea.evolve(generator=wrapper.generator,
                          evaluator=wrapper.evaluator,
                          pop_size=100,
                          bounder=wrapper.bounder,
                          maximize=False,
                          max_generations=200,
                          statistics_file=stats_file,
                          individuals_file=individuals_file)

    # Save the final population archive  to CSV files
    stats_file = open('{}-{}-final-statistics-file.csv'.format(script_name, 'harmonic' if harmonic else 'monthly'), 'w')
    individuals_file = open('{}-{}-final-individuals-file.csv'.format(script_name, 'harmonic' if harmonic else 'monthly'), 'w')
    inspyred.ec.observers.file_observer(ea.archive, 'final', None,
                                        args={'statistics_file': stats_file, 'individuals_file': individuals_file})

    if display:
        final_arc = ea.archive
        print('Best Solutions: \n')
        for f in final_arc:
            print(f)

        x = []
        y = []

        for f in final_arc:
            x.append(f.fitness[0])
            y.append(f.fitness[1])

        plt.scatter(x, y, c='b')
        plt.xlabel('Total demand deficit [Ml/d]')
        plt.ylabel('Total Transferred volume [Ml/d]')
        plt.ylim(0, 4000)
        plt.xlim(215000, 215500)
        plt.grid()
        title = 'Harmonic Control Curve' if harmonic else 'Monthly Control Curve'
        plt.savefig('{0} Example ({1}).pdf'.format(ea.__class__.__name__, title), format='pdf')
        plt.show()
    return ea


def load_individuals(filename):
    """ Read an inspyred individuals file in to two pandas.DataFrame objects.

    There is one DataFrame for the objectives and another for the variables.
    """
    import ast

    index = []
    all_objs = []
    all_vars = []
    with open(filename, 'r') as f:
        for row in f.readlines():
            gen, pop_id, objs, vars = ast.literal_eval(row.strip())
            index.append((gen, pop_id))
            all_objs.append(objs)
            all_vars.append(vars)

    index = pd.MultiIndex.from_tuples(index, names=['generation', 'individual'])
    return pd.DataFrame(all_objs, index=index), pd.DataFrame(all_vars, index=index)


def animate_generations(objective_data, colors):
    """
    Animate the pareto frontier plot over the saved generations.
    """
    import matplotlib.animation as animation

    def update_line(gen, dfs, ax, xmax, ymax):
        ax.cla()
        artists = []
        for i in range(gen+1):
            for c, key in zip(colors, sorted(dfs.keys())):
                df = dfs[key]

                scat = ax.scatter(df.loc[i][0], df.loc[i][1], alpha=0.8**(gen-i), color=c,
                              label=key if i == gen else None, clip_on=True, zorder=100)
                artists.append(scat)

        ax.set_title('Generation: {:d}'.format(gen))
        ax.set_xlabel('Total demand deficit [Ml/d]')
        ax.set_ylabel('Total Transferred volume [Ml/d]')
        ax.set_xlim(0, xmax)
        ax.set_ylim(0, ymax)
        ax.legend()
        ax.grid()
        return artists

    fig, ax = plt.subplots(figsize=(10, 10))
    last_gen = list(objective_data.values())[0].index[-1][0]
    last_gen = int(last_gen)

    xmax = max(df.loc[last_gen][0].max() for df in objective_data.values())
    ymax = max(df.loc[last_gen][1].max() for df in objective_data.values())

    line_ani = animation.FuncAnimation(fig, update_line, last_gen+1,
                                       fargs=(objective_data, ax, xmax, ymax), interval=400, repeat=False)

    line_ani.save('generations.mp4', bitrate=1024,)
    fig.savefig('generations.png')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--harmonic', action='store_true', help='Use an harmonic control curve.')
    parser.add_argument('--plot', action='store_true', help='Plot the pareto frontier.')
    parser.add_argument('--library', type=str, choices=['inspyred', 'platypus', 'pygmo'])
    args = parser.parse_args()

    if args.plot:
        objs, vars = {}, {}
        for cctype in ('monthly', 'harmonic'):
            objs[cctype], vars[cctype] = load_individuals('two_reservoir_moea-{}-individuals-file.csv'.format(cctype))

        animate_generations(objs, ('b', 'r'))
        plt.show()
    else:
        if args.library == 'inspyred':
            inspyred_main(display=True, harmonic=args.harmonic)
        elif args.library == 'platypus':
            platypus_main(harmonic=args.harmonic)
        elif args.library == 'pygmo':
            pygmo_main(harmonic=args.harmonic)
        else:
            raise ValueError('Optimisation library "{}" not recognised.'.format(args.library))
