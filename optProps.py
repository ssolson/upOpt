from utilities import (getUserProperty, kingOfTheStreet, collectionsDict, 
                       getCollections, write_solution, check_active_colletions,
                       get_user_properties_data)
from ILP import optimizeCollection
from sys import argv
import pandas as pd
from os import path
import numpy as np
import itertools 
import requests
import timeit 
import pulp
import sys
import ast

def optimizeCollections(username, write=False):
    '''
    Runs an integer linear programming optimization for a user'seek
    properties by splitting up the problem into 2 categories (high and 
    low yield collection).
    
    Parameters
    ----------
    username: string
        username to query
    write: bool
        optional, default False. If True write solution to txt file
    
    Returns
    -------
    collection: dict
        dictionary of collection optimization solution
    '''

    allCollections = getCollections()

    username=argv[1]
    properties = getUserProperty(username)
    propertiesRemaining = properties.copy(deep=True)

    allDVData = collectionsDict(properties, allCollections) 


    allDVData = allDVData[allDVData.collectionID != 1]    
    allDVData.sort_values('yield_per_hour', ascending=False, inplace=True) 

    #=======================================================================
    # Optimize the High Yield Collections first
    #=======================================================================
    dvData = allDVData.copy(deep=True)
    solutions={}
    #-----------------------------------------------------------------------
    # High Yield DVs
    #-----------------------------------------------------------------------
    # Do not optimize newbie(7), SFian(11), King of street(1), or city pro(21) yet
    lowYieldIDs = allCollections[allCollections.yield_boost <= 1.4].id.to_list()
    optimizeOver= set(dvData.collectionID.values.tolist()) - set(lowYieldIDs)
    highYieldDVs = dvData[dvData.collectionID.isin(optimizeOver)]
    
    prob = optimizeCollection(highYieldDVs, allCollections)
    # Each of the variables is printed with it's resolved optimum value
    for collectionID in highYieldDVs.collectionID.unique(): 
        solutions[int(collectionID)] = []
    for v in prob.variables():
        collectionID = v.name.split('_')[2]
        propertyID = v.name.split('_')[1]
        if v.value() == 1:
            solutions[int(collectionID)].extend([propertyID])
            # Remove property from dvData
            idx = dvData[dvData['propertyID'] == int(propertyID)].index        
            dvData.drop(index=idx, inplace=True)
                        
            propertiesRemaining.drop(index=int(propertyID), inplace=True)

    #-------------------------------------------------------------------
    # Low Yield DVs
    #-------------------------------------------------------------------
    kingData = kingOfTheStreet(propertiesRemaining)
    allDVData = allDVData.append(kingData)
    dvData = dvData.append(kingData)
    
    lowYieldDVs = dvData[dvData.collectionID.isin(lowYieldIDs)]   
    #import ipdb; ipdb.set_trace()
    prob = optimizeCollection(lowYieldDVs, allCollections)
    # Each of the variables is printed with it's resolved optimum value
    for collectionID in lowYieldDVs.collectionID.unique(): 
        solutions[int(collectionID)] = []
    for v in prob.variables():
        collectionID = v.name.split('_')[2]
        propertyID = v.name.split('_')[1]
        if v.value() == 1:
            solutions[int(collectionID)].extend([propertyID])

    #===================================================================
    # Solution to Dictionary
    #===================================================================
    baseYieldPerHour = properties.yield_per_hour.sum()
    collectionBoost = {}
    yieldFromCollections = 0
    for collectionID, props in solutions.items():
        collectionYield = 0
        collection = allCollections[allCollections['id'] == collectionID]
        yieldBoost = collection.yield_boost.values[0]
        
        for propID in props: 
            propYield = properties.loc[int(propID)].yield_per_hour
            collectionYield += yieldBoost * propYield - propYield
        
        yieldFromCollections += collectionYield
        collectionBoost[collectionID] = collectionYield

    monthlyBaseEarnings =  baseYieldPerHour * 24 * 30
    monthlyBoostEarnings = yieldFromCollections * 24 * 30
    monthlyUPX = monthlyBaseEarnings + monthlyBoostEarnings
        
    print(f'Monthly UPX: {monthlyUPX}')
    collection = {'ILPSolution' : solutions}
    collection['earnings'] = {'base_earnings': monthlyBaseEarnings,
                              'collection_earnings': monthlyBoostEarnings,
                              'total_earnings': monthlyUPX,
                              'active_collections': len(solutions)
                             }      
    
    collections={}
    allDVCollectionIDsSorted = np.sort(allDVData.collectionID.unique())
    for collectionID in allDVCollectionIDsSorted:         
        collectionName = allCollections[allCollections.id == int(collectionID)].name.values[0]        
        N = allCollections[allCollections.id == int(collectionID)].amount.values[0]
        monthlyBoost = collectionBoost[collectionID]* 24 * 30 

        collections[collectionID] = {'name' : collectionName,
                                    'number_needed': N,
                                    'collection_boost' :yieldBoost,
                                    'monthly_earnings': monthlyBoost,
                                   }                                   
        addresses={}
        for i in range(N):
            try:
                prop = solutions[int(collectionID)][i]
            except:
                print(f'ERROR: Need {N} properties in {collectionName}')
            else:         
                addressName = properties.loc[int(prop)].full_address
                mintPrice = properties.loc[int(prop)].mint_price
                
                address={'mint' : properties.loc[int(prop)].mint_price,
                         'id' : prop
                        }
                addresses[addressName] = address
        collections[collectionID]['properties'] = addresses
    collection['collections'] = collections
                  
    if write:     
        write_solution(username, collection)
                     
    return collection

          
    
    
if __name__ == '__main__':    
    username = argv[1]        
    optimized = optimizeCollections(username, write=True)
    try:
        f = open("key.txt", "r")
    except:
        auth = None
    else:
        auth = f.read()
    
    if auth:   
        user_properties = get_user_properties_data(auth)        
        optimized = check_active_colletions(user_properties, optimized)
        write_solution(username, optimized)
    import ipdb; ipdb.set_trace()
                