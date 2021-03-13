import pandas as pd
import numpy as np
import requests
import sys

def getCollections():
    '''
    Queries Upland's API for all collections
    
    Paramters
    ---------
    None
    
    Returns
    -------
    allCollections: DataFrame
        DataFrame of all collections
    '''    
    response = requests.get(f'https://api.upland.me/collections')
    allCollections = pd.DataFrame(response.json())
    allCollections.sort_values('yield_boost', ascending=False, inplace=True)
    allCollections.reset_index(inplace=True)
    return allCollections


def getUserProperty(username):
    '''
	Requests the user's properties from Uplandworld and returns a 
	DataFrame
	
	Parameters
	----------
	username: str
	    Upland username
	Returns
	-------
	properties: DataFrame
	    Dataframe of all user properties
	'''
    response = requests.get(f'https://api.uplandworld.me/upland/{username}' )
    propsDict = response.json()['data']['properties'] 	
    properties = pd.DataFrame(propsDict) 
    properties = properties.replace('Unknown', np.NaN)
    properties['_id'] = pd.to_numeric( properties['_id'])
    properties = properties.set_index('_id')

    #Remove unused columns
    cols = ['owner', 'mint_price', 'prop_id',
            'neighborhood', 'city_id', 'neighborhood_id',
           'full_address', 'up2', 'city', 'country', 'yield_per_hour',
           'lat', 'lng', 'collections', 'timestamp', 'street_id' ]
    unwantedCols = set(properties.keys()) - set(cols) 
    for col in unwantedCols:
        del properties[col]
        
    #properties['prop_id']=properties.astype({'prop_id':'int64'}).prop_id
    #properties['city_id']=properties.astype({'city_id':'int32'}).city_id
    #properties['street_id']=properties.astype({'street_id':'int64'}).street_id
    return properties

def defineDV(yield_per_hour,collectionID, yieldBoost, propID,
             cityID, streetID, address ):
    '''
    Defines DV Vars
    
    Parameters
    ----------
    
    Returns
    -------
    Dictionary
        Dictionray with araible defined
    '''
    return { 'yield_per_hour' : yield_per_hour,
             'collectionID': collectionID,
             'collectionBoost': yieldBoost,
             'propertyID' : propID,
             'cityID' : cityID,
             'streetID' : streetID,
             'address' : address
             }
     
                                         
def kingOfTheStreet(properties, NMaxStreets=2, NPropertiesMax=4):
    '''
    Creates kingOfTheStreet decsion variables
    
    Parameters
    ----------
    properties: DataFrame
        All user properties
    maxStreets: int
        maximum number of streets (streetIDs) to optimized
    maxProperties: int
        maximum number of propeties on a single street to consider
    
    Returns
    -------
    kingData: DataFrame
        King of the Street Decision variables
    '''
    collectionID = 1
    yieldBoost=1.3
    NNeeded=3

    kingOfStreetIDs = {}
    for name, group in properties.groupby('street_id')['prop_id']:
        if len(group) >= NNeeded:
            kingOfStreetIDs[name] = group


    # Create king of the street decision variables
    kingDict={}        
    for streetID, propIDs in kingOfStreetIDs.items():
        for propID in propIDs:
            #import ipdb; ipdb.set_trace() 
            address = properties.loc[int(propID)].full_address
            yield_per_hour = properties.loc[int(propID)].yield_per_hour
            cityID = properties.loc[int(propID)].city_id
            decisionVariable = f'{propID}_{collectionID}_{cityID}_{streetID}'
            kingDict[decisionVariable] = defineDV( yield_per_hour,
                                                   collectionID, yieldBoost, 
                                                   propID, cityID, streetID, 
                                                   address )
                    
        
    kingData = pd.DataFrame(kingDict).T   
    kingData['collectionID']=kingData.astype({'collectionID':'int32'}).collectionID
    kingData['propertyID']=kingData.astype({'propertyID':'int64'}).propertyID
    kingData['cityID']=kingData.astype({'cityID':'int32'}).cityID 
    kingData['streetID']=kingData.astype({'streetID':'int32'}).streetID     
    
    # Only keep N streets in each city with largest return
    for streetID in kingData.streetID.unique():
        streetData = kingData[kingData['streetID'] == streetID].copy(deep=True)       
        if len(streetData) > NPropertiesMax:
            streetData.sort_values('yield_per_hour', ascending=False, inplace=True) 
            rmID =  streetData.index[-(len(streetData)-NPropertiesMax):]
            kingData.drop(index=rmID, inplace=True)
    
    # maxStreets per city 
    for cityID in kingData.cityID.unique():
        cityData = kingData[kingData['cityID'] == cityID].copy(deep=True)        
        
        if len(cityData) > NMaxStreets:
            streetYield={}
            for streetID in cityData.streetID.unique():
                streetYield[streetID] = cityData[cityData['streetID'] == streetID].yield_per_hour.sum()
            sumStreetYield = pd.DataFrame([streetYield]).T    
            sortedStreetYield = sumStreetYield[0].sort_values(ascending=False)
           
            removeStreets = sortedStreetYield[NMaxStreets:]
            for streetID in removeStreets.index:
                rmID =  cityData[cityData['streetID']==streetID].index
                kingData.drop(index=rmID, inplace=True)
    #import ipdb; ipdb.set_trace()
    return kingData

 
def collectionsDict(properties, allCollections, NKeep=30):
    '''
    Iterates over properties dict to create a dataframe of needed vars. 
    Removes more than the set number of NKeep for cityPro, Newbie, SFian
     
    Parameters
    ----------
    properties: DataFrame
        All user properties
    allCollections: Dict
        All possible collections and the number need
     
     Returns
     -------
     dvData: DataFrame
         Decision Variables
     '''
    dvDict={}    
       
    # Create decision variables for each propertie's possible collections
    for propID, details in properties.iterrows():       
        cityID = details.city_id
        yield_per_hour = details.yield_per_hour
        address = details.full_address
        streetID = details.street_id
        #import ipdb; ipdb.set_trace()
        try:
            propCollections = pd.DataFrame(details.collections)  
        except:
            print(f'Property: {propID} has no associated collection')
            # Manually Add Newbie ['7']
            collectionID = 7
            collectionBoost = 1.1
            decisionVariable = f'{propID}_{collectionID}_{cityID}'
            
            dvDict[decisionVariable] = defineDV( yield_per_hour,
                                               collectionID, collectionBoost, 
                                               propID, cityID, streetID, 
                                               address )
            # Manually Add City Pro ['21']
            collectionID = 21
            collectionBoost = 1.4
            decisionVariable = f'{propID}_{collectionID}_{cityID}'
            dvDict[decisionVariable] = defineDV( yield_per_hour,
                                               collectionID, collectionBoost, 
                                               propID, cityID, streetID, 
                                               address )                                            
            if cityID == 1:
                # Manually add San Franciscan 
                collectionID = 11
                collectionBoost = 1.2
                decisionVariable = f'{propID}_{collectionID}_{cityID}'
                dvDict[decisionVariable] = defineDV( yield_per_hour,
                                               collectionID, collectionBoost, 
                                               propID, cityID, streetID, 
                                               address )                            
        else:                        
            for idx, collectionDetails in propCollections.iterrows():                
                collectionID = collectionDetails['id']
                collectionBoost = collectionDetails.yield_boost
                
                decisionVariable = f'{propID}_{collectionID}_{cityID}'
                dvDict[decisionVariable] = defineDV( yield_per_hour,
                                               collectionID, collectionBoost, 
                                               propID, cityID, streetID, 
                                               address )
                     
    dvData = pd.DataFrame(dvDict).T

    dvData['collectionID']=dvData.astype({'collectionID':'int32'}).collectionID
    dvData['propertyID']=dvData.astype({'propertyID':'int64'}).propertyID
    dvData['cityID']=dvData.astype({'cityID':'int32'}).cityID
    dvData['yield_per_hour']=pd.to_numeric( dvData.yield_per_hour)
    
    # Remove Collections which do not meet minimum number needed
    for collectionID in dvData.collectionID.unique():     
        NNeeded = allCollections[allCollections['id']==collectionID].amount.values
        NPossiblePropsInCollection = len(dvData[dvData['collectionID']==collectionID])
                
        if NPossiblePropsInCollection < NNeeded:                
            print(f'Not Enough Properties for: {allCollections[allCollections["id"]==collectionID].name.values}')
            rmID = dvData[dvData['collectionID']==collectionID].index
            dvData.drop(index=rmID, inplace=True) 
    
    #Only keep Top NKeep Newbie 
    NNewbie = (dvData.collectionID == 7).sum()    
    if NNewbie > NKeep:
       dvData['yield_per_hour']=pd.to_numeric( dvData.yield_per_hour)
       rmId =  dvData[dvData.collectionID==7].nsmallest(
                      columns='yield_per_hour', n=NNewbie-NKeep).index
       dvData.drop(index=rmId, inplace=True)

    #Only keep Top NKeep SFian 
    NSFian = (dvData.collectionID == 11).sum()    
    if NSFian > (NKeep+30):
       dvData['yield_per_hour']=pd.to_numeric( dvData.yield_per_hour)
       rmId =  dvData[dvData.collectionID==11].nsmallest(
                      columns='yield_per_hour', n=NSFian-(NKeep+30)).index
       dvData.drop(index=rmId, inplace=True)       
       
    # Only top NKeep per city in City Pro
    for cityID in dvData.cityID.unique():
        cityProps = dvData[dvData['cityID']==cityID].copy(deep=True)
        cityProProps = cityProps[cityProps['collectionID']==21].copy(deep=True)
        NCityPro  = len(cityProProps)
        NNeeded = allCollections[allCollections['id']==21].amount.values
        #import ipdb; ipdb.set_trace()
        if NCityPro < NNeeded:
            print(f'Not Enough Properties for City Pro CItyID: {cityID}')
            rmID = cityProProps.index
            dvData.drop(index=rmID, inplace=True) 
        
        if (NCityPro > NKeep) and (cityID != 1):
           cityProProps.sort_values('yield_per_hour', ascending=False, inplace=True)          
           rmID =  cityProProps.index[-(NCityPro-NKeep):]
           #import ipdb; ipdb.set_trace()           
           dvData.drop(index=rmID, inplace=True)  
        elif (NCityPro > (NKeep+60)) and (cityID == 1):
           cityProProps.sort_values('yield_per_hour', ascending=False, inplace=True)          
           rmID =  cityProProps.index[-(NCityPro-(NKeep+60)):]
           #import ipdb; ipdb.set_trace()           
           dvData.drop(index=rmID, inplace=True)             
                      
           del cityProProps
    return dvData


def write_solution(username, solution):  
    '''
    Writes the solution to file
    
    Parameters
    ----------
    username: str
       user name       
    solution: dictionary
        solution dictionary
    Returns
    -------
    None: 
        Writes f'{username.txt}' to file
    ''' 
    allCollections = getCollections()    

    monthlyBaseEarnings = solution['earnings']['base_earnings']
    monthlyBoostEarnings = solution['earnings']['collection_earnings']
    monthlyUPX = solution['earnings']['total_earnings']    
    NActive = len(solution['ILPSolution'])
    
    with open(f'{username}.txt', "w") as f:
        f.write('=======================================================\n')
        f.write(f'UPX Per Month\n')
        f.write('=======================================================\n')
        f.write(f'Base               : {monthlyBaseEarnings.round()}\n')
        f.write(f'Collections        : {monthlyBoostEarnings.round()}\n')
        f.write(f'Total              : {monthlyUPX.round()}\n')
        f.write(f'Active Collections : {NActive}\n\n')
        
        for collectionID in solution['collections']:  
            monthlyBoost = solution['collections'][collectionID]['monthly_earnings']        
            collectionName = solution['collections'][collectionID]['name']
            N = solution['collections'][collectionID]['number_needed']

            if isinstance(monthlyBoost, float): 
                monthlyBoost = monthlyBoost.round(0)
            f.write('=======================================================\n') 
            f.write(f'{collectionName}({collectionID}): [{N} Properties: {monthlyBoost} UPX/month]\n')
            f.write('=======================================================\n')
            i=0
            for address in solution['collections'][collectionID]['properties']:      
                mintPrice = solution['collections'][collectionID]['properties'][address]['mint']
                try:
                    active = solution['collections'][collectionID]['properties'][address]['active']
                except:
                    f.write(f'{i+1}. {address}    (Mint: {mintPrice/1000} k )\n')
                else:
                    if active:
                        status='Active'
                    else:
                        status='Inactive'
                    f.write(f'{i+1}. {address}  [{status}]  (Mint: {mintPrice/1000} k )\n')               
                i+=1
            f.write('\n')       
        original_stdout = sys.stdout   

def check_active_colletions(user_properties, optimized):
    '''
    This will return the user's active collection property IDs
    
    Parameters
    ----------
    user_properties: DataFrame
        All user's properties
    Returns
    -------
    optimized: dictionary
        returns optimized solution with new boolean 'active' key added 
        to each property
    '''
    allCollections = getCollections()
    active = user_properties[user_properties.collection_boost !=1].copy(deep=True)
    for collectionID, props in optimized['ILPSolution'].items():
        for propID in props:
            address = active[active.prop_id == int(propID)].full_address
            if any(address): 
                address = str(address.values[0])
            
            
                collection = allCollections[allCollections['id'] == collectionID]
                collectionName = collection.name.values[0]
                yieldBoost = collection.yield_boost.values[0]
                solutionInActive = any(active.prop_id == int(propID))
                if solutionInActive:
                    activeBoost = active[active.prop_id == int(propID)].collection_boost
                    boostMatch = float(activeBoost) == yieldBoost
                    if boostMatch:
                        optimized['collections'][collectionID]['properties'][address]['active'] = True
    return optimized  
    
    
def get_user_properties_data(auth):
    '''
    This will retun a user's current properties when the auth key is 
    passed.
    
    Parameters
    ----------
    auth: str
        Authentication token
    
    Returns
    -------
    user_properties: DataFrame
        Dataframe of current active collections    
    '''
    url = "https://api.upland.me/yield/mine"
    header = {"Authorization":auth}
    response = requests.get(url, headers=header)
    user_properties = pd.DataFrame(response.json())
    return user_properties    