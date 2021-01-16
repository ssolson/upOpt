from utilities import getUserProperty, kingOfTheStreet, collectionsDict
import pandas as pd
from os import path
import numpy as np
import itertools 
import requests
import timeit 
import pulp
import sys


def cityProConstraint(prob, dvData, modelVars):
    '''
    #City Pro group constraints ('21')
    #    If propInCityN0 then not any prop in city N to N+1
    
    Parameters
    ----------
    prob: Pulp Object
        the ILP problem definition 
    dvData: DataFrame
        decsion variables
    modelVars: Dict
        Dictionary of PuLP model decision variables 
        
    Returns
    -------
    prob: PuLP Object
        problem with city pro constraints added
    '''     
    print('CONSTRAINT: City Pro All City Properties in 1 City')

    propsInCity={}
    cityProProps = dvData[dvData['collectionID']==21].copy()
        
    
    for cityID in cityProProps.cityID.unique():
       propsInCity[str(cityID)] = cityProProps[cityProProps['cityID']==cityID].index.to_list()        
        
    propsPerCity=[]
    for city in propsInCity:
        propsPerCity.append(propsInCity[str(city)])
      
    # Create constraint of all possible permutations 
    uniqueDifferentCityProps = list(itertools.product(*propsPerCity)) 
    #import ipdb; ipdb.set_trace()
    for combination in uniqueDifferentCityProps:    
        prob += (pulp.lpSum([modelVars[dv] for dv in combination])
                  ) <=1, f'{combination}'
              

    del cityProProps    
    return prob


def kingOfStreetConstraint(prob, dvData, modelVars):
    '''
    King of the Street ('1') on the same street   
    
    Parameters
    ----------
    prob: Pulp Object
        the ILP problem definition 
    dvData: DataFrame
        decsion variables
    modelVars: Dict
        Dictionary of PuLP model decision variables    
    
    Returns
    -------
    prob: PuLP Object
        problem with city pro constraints added
    '''          
    print('CONSTRAINT: King of The Street All Properties on 1 Street')
    propsOnStreet={}
    kingOfStProps = dvData[dvData['collectionID']==1].copy(deep=True)

    for streetID in kingOfStProps.streetID.unique():
        propsOnStreet[streetID] = kingOfStProps[kingOfStProps['streetID']==streetID].index.to_list()

    #import ipdb;ipdb.set_trace()
    propsPerStreet=[]
    for streetID in propsOnStreet:
        propsPerStreet.append(propsOnStreet[streetID])

    # Create constraint of all possible permutations 
    uniqueDifferentStreetProps = list(itertools.product(*propsPerStreet)) 

    print('Adding Streets to ILP Problem')
    for combination in uniqueDifferentStreetProps:    
        prob += (pulp.lpSum([modelVars[dv] for dv in combination])) <=1, f'{combination}'
    print('Done')
    del kingOfStProps  
    #import ipdb;ipdb.set_trace() 
    return prob  
        

def optimizeCollection(dvData, allCollections, collectionIDs=None):
    '''
    Interger linear programming over the decsion variables
    
    Parameters
    ----------
    dvData: DataFrame
        DataFrame of decsion variables
    allCollections: DataFrame
        All COllections
    collectionIDs: list 
        If specified subset of collection IDs to consider
    
    
    Returns
    -------
    prob: PuLP Object
        LP solution
    '''
    # Create the 'prob' variable to contain the problem data
    prob = pulp.LpProblem("Collections", pulp.LpMaximize)

    # A dictionary called 'model_vars' is created to contain the variables 
    modelVars = pulp.LpVariable.dicts("",dvData.index,0, cat=pulp.LpBinary)

    # The objective function is added to 'prob' first
    prob +=  pulp.lpSum([data.collectionBoost * data.yield_per_hour * modelVars[dv] 
                         for dv,data in dvData.iterrows()]), "UPX"


    # CONSTRAINTS
    #=======================================
    # Only 1 collection per property
    #=======================================
    print('CONSTRAINT: Only 1 Collection Per Property')
    for propertyID in dvData.propertyID.unique():
        propertyDVs = dvData[dvData['propertyID']==propertyID].index.tolist()
        allPropCollections = [modelVars[dv] for dv in propertyDVs]
        prob += (pulp.lpSum(allPropCollections)) <=1, f'{propertyID}Only1Collection'


    #=======================================================                      
    # Max Number of properties in Collection Constraints 
    #======================================================
    print('CONSTRAINT: Max Number of Properties Per Collection')
    for collectionID in dvData.collectionID.unique():   
        collection = allCollections[allCollections.id == collectionID]
        collectionName = collection.name
        NNeeded = collection.amount
        propsInCollection = dvData[dvData['collectionID']==collectionID].index.to_list()
        prob += (pulp.lpSum( [modelVars[dv] for dv in propsInCollection ])) <= NNeeded , f'{NNeeded} Properties In {collectionName}' 
    
    #import ipdb;ipdb.set_trace() 
    if any(dvData.collectionID.isin([21])):
        prob = cityProConstraint(prob, dvData, modelVars)
    if any(dvData.collectionID.isin([1])):        
        prob = kingOfStreetConstraint(prob, dvData, modelVars)
    #import ipdb; ipdb.set_trace()
    # The problem data is written to an .lp file
    prob.writeLP("Collections.lp")

    # The problem is solved using PuLP's choice of Solver
    print('Solving')
    prob.solve()

    # The status of the solution is printed to the screen
    print(f'Status: {pulp.LpStatus[prob.status]}')

    return prob    
                      
#import ipdb; ipdb.set_trace()

