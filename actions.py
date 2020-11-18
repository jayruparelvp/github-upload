from rasa_sdk.forms import FormAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet, FollowupAction, AllSlotsReset
from typing import Text, List, Dict, Any
import mysql.connector
import json
import re
import mpu
from emailcheck import SendEmailOrder
cnx = mysql.connector.connect(buffered=True,user='root', password='voiceplug', database='voiceplugorder')
mycursor = cnx.cursor()
entity_value = []

def showInfo(group,category,subcategory,dispatcher:CollectingDispatcher):
    if group: catgroup = group
    elif subcategory: catgroup = subcategory
    elif category: catgroup = category
    sql = "SELECT item_name FROM mipmenucatgroup WHERE catgroup_name = %s"
    choice = (catgroup,)
    mycursor.execute(sql,choice)
    myresult = mycursor.fetchall()
    string,i = "",0
    if myresult:
       dispatcher.utter_message("We have the following choices of {} on our menu".format(catgroup))
       for x in myresult:
          if i==0 :string = string + str(x[0])
          else: string = string + "," + str(x[0])
          i=i+1
       dispatcher.utter_message("{}".format(string))
       dispatcher.utter_message("What would you like to order".format())
    else: dispatcher.utter_message("There are no items on our menu that match {}. To know whats on our menu say MENU".format(catgroup))

class CurrentItem:
    def __init__(self):
        self.name = ""
        self.qty = ""
        self.size = ""
        self.ing = []
        self.itemList =[]
        self.itmtoflag=False
        self.itmtoname=''
        self.entity_value=[]
    def dict_toClass(self,my_json):
        my_dict = json.loads(my_json)
        for key in my_dict:
            setattr(self, key, my_dict[key])
        return self
#######  Sets the query for ingrediens, size, qty for the item - mainly used for ingredients
    def set_query_ing(self,entity,entity_name,indx,entity_role,itmtoflag,itmtoname):
        if(entity_role=='from'):
           if(itmtoflag):
               self.ing.append({'name':{entity_name:itmtoname},'entity':entity,'role':entity_role})
               self.itmtoflag=False
               self.itmtoname=''
           else:
               if indx<len(self.entity_value):
                  self.ing.append({'name':{entity_name:self.entity_value[indx]['value']},'entity':entity,'role':entity_role})
                  self.itmtoflag=True
        else:
            if(entity_role=='exclude' or entity_role=='include'):
               self.ing.append({'name':entity_name,'entity':entity,'role':entity_role})
               self.itmtoflag=False
               self.itmname=''
    def set_query(self,entity_value,item,oper):
        startList=[]
        self.entity_value=entity_value
        #Find the Starting positions of item in the query
        for a in item:
            for b in range(len(entity_value)):
                if (entity_value[b]['value']==a): startList.append(entity_value[b]['start'])
#        print("length of current query",len(startList),startList,item,entity_value)
        if(len(self.itemList)==0):
           for a in item:
              #newitem = CurrentItem()
              self.name=a
              self.itmtoflag=False
              self.itmtoname=''
              ## For the  current items set the ingredients and other attributes
              for b in range(len(entity_value)):
                    if (a==entity_value[b]['value']):
                        gp=entity_value[b]['group'] if 'group' in entity_value[b].keys() else ""
                        for l in range(len(entity_value)):
                            if (entity_value[l]['entity']=='qty' and 'group' in entity_value[l].keys()):
                               if (entity_value[l]['group'] == gp ): self.qty=entity_value[l]['value']
                            if (entity_value[l]['entity']=='size' and 'group' in entity_value[l].keys()):
                               if (entity_value[l]['group'] == gp ): self.size=entity_value[l]['value']
########### Checks for ingredients  for build query  and editquery
                            if (entity_value[l]['entity']=='item'):
                                self.itmtoflag =  False
                                self.itmtoname=''
                            if ("ing" in entity_value[l]['entity'] and 'role' in entity_value[l].keys() and entity_value[l]['role']=='to'):
                               if (self.itmtoflag):
                                    self.itmtoflag=False
                                    self.itmtoname=''
                               else:
                                   self.itmtoflag=True
                                   self.itmtoname=entity_value[l]['value']
#                            print(entity_value[l]['entity'],entity_value[l]['start'],startList[item.index(a)],item.index(a)+1,len(startList),self.itmtoflag,self.itmtoname)
############################ Checks if this is the last item , for buildquery  it should check ing after the current item and before the next item
############################# but for editquery  it should check after prev item and before the current  item
                            if (item.index(a)+1<len(startList)):
                                if (oper=='buildquery'):
                                   if ("ing" in entity_value[l]['entity'] and 'role' in entity_value[l].keys() and (entity_value[l]['start'] > startList[item.index(a)] and entity_value[l]['start']< startList[item.index(a)+1])):
                                      self.set_query_ing(entity_value[l]['entity'],entity_value[l]['value'],l+1,entity_value[l]['role'],self.itmtoflag,self.itmtoname)
                                else:
                                   if (oper =='remove_ing'): role='exclude'
                                   elif (oper == 'add_ing'): role='include'
                                   else: role = entity_value[l]['role']  if ('role' in entity_value[l].keys()) else ""
                                   if (item.index(a)==0):
                                      if ("ing" in entity_value[l]['entity'] and entity_value[l]['start'] < startList[item.index(a)]):
                                         self.set_query_ing(entity_value[l]['entity'],entity_value[l]['value'],l+1,role,self.itmtoflag,self.itmtoname)
                                   else:
                                      if ("ing" in entity_value[l]['entity'] and (entity_value[l]['start'] > startList[item.index(a)-1] and entity_value[l]['start'] < startList[item.index(a)])):
                                         self.set_query_ing(entity_value[l]['entity'],entity_value[l]['value'],l+1,role,self.itmtoflag,self.itmtoname)
                            else:
                                if (oper=='buildquery'):
                                    if (("ing" in entity_value[l]['entity']) and 'role' in entity_value[l].keys() and (entity_value[l]['start'] > startList[item.index(a)])):
                                        self.set_query_ing(entity_value[l]['entity'],entity_value[l]['value'],l+1,entity_value[l]['role'],self.itmtoflag,self.itmtoname)
                                else:
                                    if (oper == 'remove_ing'): role='exclude'
                                    elif (oper == 'add_ing'): role='include'
                                    else: role  = entity_value[l]['role']  if ('role' in entity_value[l].keys())  else ""
                                    if (item.index(a)==0):
                                        if ("ing" in entity_value[l]['entity'] and entity_value[l]['start'] < startList[item.index(a)]):
                                            self.set_query_ing(entity_value[l]['entity'],entity_value[l]['value'],l+1,role,self.itmtoflag,self.itmtoname)
                                    else:
                                        if ("ing" in entity_value[l]['entity'] and (entity_value[l]['start'] > startList[item.index(a)-1] and entity_value[l]['start'] < startList[item.index(a)])):
                                            self.set_query_ing(entity_value[l]['entity'],entity_value[l]['value'],l+1,role,self.itmtoflag,self.itmtoname)
                        self.itemList.append({'name':self.name,'qty':self.qty,'size':self.size,'cust':self.ing})
#                        for i in (range(len(self.itemList))): print(self.itemList[i]['name'],self.itemList[i]['cust'])
                        self.ing=[]

class StartAction(Action):
    def name(self) -> Text:
        return "start_action"
    def run(self, dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        rest_location = tracker.get_slot("rest_location")
        rest_deliver = tracker.get_slot("rest_deliver")
        sql = "Select rest_name, num_location, rest_deliver from restdetails where rest_name = 'My Indian Pizza'"
        mycursor.execute(sql)
        myresult=mycursor.fetchone()
        if myresult:
           rest_name = myresult[0]
           num_location = myresult[1]
           rest_deliver = myresult[2].lower()
        if (num_location == 1): rest_location = "single"
        else: rest_location = "multiple"
        dispatcher.utter_message("Welcome to {}".format(rest_name))
        return[SlotSet("rest_deliver",rest_deliver),SlotSet("rest_location",rest_location),SlotSet("deliver_type",rest_deliver)]

class InquireItemAction(Action):
    def name(self) -> Text:
        return "inquire_item_action"
    def run(self, dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        item =  tracker.get_slot("item")
        category = tracker.get_slot("category")
        group = tracker.get_slot("group")
        subcategory = tracker.get_slot("subcategory")
        if item == None: item = []
        if (item or category or group or subcategory):
            if (len(item) > 0):
               sql = "select item_name,size_options from mipmenuitems where item_name = %s"
               choice = (item[0],)
               mycursor.execute(sql,choice)
               myresult = mycursor.fetchone()
               if myresult: dispatcher.utter_message("{} is available on our menu in {} size. To order any item say the item name. To know the items on our menu say MENU".format(myresult[0],myresult[1]))
               else: dispatcher.utter_message("There are no items on our menu that match {}. To know whats on our menu say MENU".format(item[0]))
               return[SlotSet("item",None)]
            else:
               if (group or category or subcategory):
                  showInfo(group,category,subcategory,dispatcher)
               return[SlotSet("group",None),SlotSet("subcategory",None),SlotSet("category",None)]
        else:
           dispatcher.utter_message("There are no such items on our menu. To know whats on our menu, say MENU".format())
           return[]

class AskSizeOptionsAction(Action):
    def name(self) -> Text:
        return "ask_size_options_action"
    def run(self, dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        item =  tracker.get_slot("item")
        if item == None: item = []
        if (len(item) > 0):
           sql = "select item_name,size_options from mipmenuitems where item_name = %s"
           choice = (item[0],)
           mycursor.execute(sql,choice)
           myresult = mycursor.fetchone()
           if myresult: dispatcher.utter_message("{} is available in {} size. To order any item say the item name. To know the items on our menu say MENU".format(myresult[0],myresult[1]))
           else: dispatcher.utter_message("There are no items on our menu that match {}. To know whats on our menu say MENU".format(item[0]))
           return[SlotSet("item",None)]
        else:
           dispatcher.utter_message("There are no such items on our menu. To know whats on our menu, say MENU".format())
           return[]

class FindItem(Action):
    def name(self) -> Text:
        return "find_item"
    def run(self, dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
#        print("\n")
        entity_value=tracker.latest_message["entities"]
#        print("entity value", entity_value)
        category = tracker.get_slot("category")
        group = tracker.get_slot("group")
        subcategory = tracker.get_slot("subcategory")
        item =  tracker.get_slot("item")
        currentQuery = tracker.get_slot("CurrentItems")
        j,k,l=0,0,0
###### Sets the items and attributtes for the currentitem
        if (item):
           if (currentQuery==None):
              newItem=CurrentItem()
              newItem.set_query(entity_value,item,'buildquery')
           else: newItem=CurrentItem().dict_toClass(currentQuery)
##### Main Logic
        order_qty_list = tracker.get_slot("order_qty_list")
        order_id_list = tracker.get_slot("order_id_list")
        item_in_list = tracker.get_slot("item_in_list")
        same_item = tracker.get_slot("same_item")
        custom_ingtype1=tracker.get_slot("custom_ingtype1")
        custom_ingtype2=tracker.get_slot("custom_ingtype2")
        custom_ingtype3=tracker.get_slot("custom_ingtype3")
        custom_ingtype4=tracker.get_slot("custom_ingtype4")
        custom_ingtype5=tracker.get_slot("custom_ingtype5")
        customize=tracker.get_slot("customize")
        if order_id_list==None: order_id_list=[]
        if order_qty_list==None: order_qty_list=[]
        if custom_ingtype1==None: custom_ingtype1=[]
        if custom_ingtype2==None: custom_ingtype2=[]
        if custom_ingtype3==None: custom_ingtype3=[]
        if custom_ingtype4==None: custom_ingtype4=[]
        if custom_ingtype5==None: custom_ingtype5=[]
        if customize==None: customize = [""]*20
        item_has_size = False
        if 'qty' not in globals(): qty = []
        if 'size' not in globals(): size = []
        print("Find Item Initial:",item,category,group,subcategory,order_id_list,order_qty_list)
        if (item or category or group or subcategory):
           if (group or subcategory or category):
              showInfo(group,category,subcategory,dispatcher)
           elif (item):
              if (item_in_list==True): qty=tracker.get_slot("qty")
              else:
                 qty=[]
                 for i in range(len(item)):
                    if (i==0): qty.append(next(tracker.get_latest_entity_values(entity_type="qty", entity_role=None, entity_group="1"),None))
                    elif (i==1): qty.append(next(tracker.get_latest_entity_values(entity_type="qty", entity_role=None, entity_group="2"),None))
                    elif (i==2): qty.append(next(tracker.get_latest_entity_values(entity_type="qty", entity_role=None, entity_group="3"),None))
                    elif (i==3): qty.append(next(tracker.get_latest_entity_values(entity_type="qty", entity_role=None, entity_group="4"),None))
              for j in qty:
                  if j is None:
                     index=qty.index(j)
                     qty[index]='1'
              if (item_in_list==True): size=tracker.get_slot("size")
              else:
                  size=[]
                  for k in range(len(item)):
                      if (k==0): size.append(next(tracker.get_latest_entity_values(entity_type="size", entity_role=None, entity_group="1"),None))
                      elif (k==1): size.append(next(tracker.get_latest_entity_values(entity_type="size", entity_role=None, entity_group="2"),None))
                      elif (k==2): size.append(next(tracker.get_latest_entity_values(entity_type="size", entity_role=None, entity_group="3"),None))
                      elif (k==3): size.append(next(tracker.get_latest_entity_values(entity_type="size", entity_role=None, entity_group="4"),None))
              print("Find_Item Later:",item,size,qty,order_id_list,order_qty_list)
              if qty:
                 if (qty[0].isdigit()==False): # check if qty entered is a valid number and if not, remove item, qty, size from the find item queue
                    dispatcher.utter_message("Please rephrase your order with a valid quantity for the items you are ordering".format())
                    qty = qty[1:]
                    item = item[1:]
                    if (size): size = size[1:]
              item_in_list = True
              if item:
#                 print("Item, size, qty earlier",item,size,qty)
#                 if (len(item)<len(size)):
#                    for i in range(len(size)-1):
#                        if size[i]item.append(item[0])
#                 print("Item, size, qty later",item,size,qty)
                 if (size) and (size[0] is not None):
                    sql = "SELECT screen_id,size,size_options,item_id,item_name,ingtype1,ingtype2,ingtype3,ingtype4,ingtype5 FROM mipmenuitems WHERE item_name = %s and size = %s"
                    choice = (item[0],size[0])
                 else:
                    sql = "SELECT screen_id,size,size_options,item_id,item_name,ingtype1,ingtype2,ingtype3,ingtype4,ingtype5 FROM mipmenuitems WHERE item_name = %s"
                    choice = (item[0],)
                 mycursor.execute(sql,choice)
                 myresult = mycursor.fetchall()
                 if myresult:
                    value=(myresult[0])
                    count=mycursor.rowcount
                    if (count > 1): # item has size but was not provided
                       dispatcher.utter_message("{} is available in {} size. What size would you like?".format(item[0],value[2]))
                       item_has_size = True
                    else: item_has_size = False # either item has size and was provided or item does nothave size
                    if len(qty)>=1: order_qty_list.append(qty[0])
                    else: order_qty_list.append(1)
                    same_item=False
# Check if item ordered is already in the cart and if so, append the additional qty ordered to existing item qty
                    new_id = [i[3] for i in myresult]
                    for order_id in order_id_list:
                       if order_id in new_id:
                          index = order_id_list.index(order_id)
                          order_qty_list[index] = int(order_qty_list[index])+int(order_qty_list[-1])
                          del order_qty_list[-1]
                          del custom_ingtype1[-1],custom_ingtype2[-1],custom_ingtype3[-1],custom_ingtype4[-1],custom_ingtype5[-1]
                          same_item=True
                    if (same_item==False and item_has_size==False):
                        order_id_list.append(myresult[0][3])
                        customize.append("")
                    dictionary_copy = json.loads(myresult[0][5]).copy()
                    custom_ingtype1.append(dictionary_copy)
                    dictionary_copy = json.loads(myresult[0][6]).copy()
                    custom_ingtype2.append(dictionary_copy)
                    dictionary_copy = json.loads(myresult[0][7]).copy()
                    custom_ingtype3.append(dictionary_copy)
                    dictionary_copy = json.loads(myresult[0][8]).copy()
                    custom_ingtype4.append(dictionary_copy)
                    dictionary_copy = json.loads(myresult[0][9]).copy()
                    custom_ingtype5.append(dictionary_copy)
#                    print("current custom values:",custom_ingtype1[-1],custom_ingtype2[-1],custom_ingtype3[-1],custom_ingtype4[-1],custom_ingtype5[-1])
                    index1=len(custom_ingtype1)-1
                    for i in range(len(newItem.itemList)):
                        if(newItem.itemList[i]['name']==item[0]):
                            for ingv in range(len((newItem.itemList[i])['cust'])):
                                if(newItem.itemList[i]['cust'][ingv]['entity'])=='ing_type1': cust_ing_type=custom_ingtype1
                                elif(newItem.itemList[i]['cust'][ingv]['entity'])=='ing_type2': cust_ing_type=custom_ingtype2
                                elif(newItem.itemList[i]['cust'][ingv]['entity'])=='ing_type3': cust_ing_type=custom_ingtype3
                                elif(newItem.itemList[i]['cust'][ingv]['entity'])=='ing_type4': cust_ing_type=custom_ingtype4
                                elif(newItem.itemList[i]['cust'][ingv]['entity'])=='ing_type5': cust_ing_type=custom_ingtype5
                                if (newItem.itemList[i]['cust'][ingv]['role']=='exclude'): customize,custom_ingtype1,ing_found=RemoveIngredientAction.remove([newItem.itemList[i]['cust'][ingv]['name']],cust_ing_type,customize,index1,item[0],dispatcher)
                                if (newItem.itemList[i]['cust'][ingv]['role']=='include'): customize,custom_ingtype1,ing_found=AddIngredientAction.add([newItem.itemList[i]['cust'][ingv]['name']],cust_ing_type,customize,index1,item[0],dispatcher)
                                if (newItem.itemList[i]['cust'][ingv]['role']=='from'):
                                    itmfrom =  next(iter((newItem.itemList[i]['cust'][ingv]['name']).keys()))
                                    itmto = next(iter((newItem.itemList[i]['cust'][ingv]['name']).values()))
                                    customize,custom_ingtype1,ing_found=SubstituteIngredientAction.substitute([itmfrom],[itmto],cust_ing_type,customize,index1,item[0],dispatcher)
        else:
           dispatcher.utter_message("There are no such items on our menu. To know whats on our menu, say MENU".format())
        return[SlotSet("group",""),SlotSet("subcategory",""),SlotSet("category",""),SlotSet("item",item),SlotSet("item_has_size",item_has_size),SlotSet("item_in_list",item_in_list),SlotSet("same_item",same_item),SlotSet("qty",qty),SlotSet("size",size),SlotSet("order_id_list",order_id_list),SlotSet("order_qty_list",order_qty_list),SlotSet("custom_ingtype1",custom_ingtype1),SlotSet("custom_ingtype2",custom_ingtype2),SlotSet("custom_ingtype3",custom_ingtype3),SlotSet("custom_ingtype4",custom_ingtype4),SlotSet("custom_ingtype5",custom_ingtype5),SlotSet("customize",customize),SlotSet("CurrentItems",json.dumps(newItem.__dict__) if item else None)]

class OrderAction(Action):
    def name(self) -> Text:
        return "order_action"
    def run(self,dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        item=tracker.get_slot("item")
        size=tracker.get_slot("size")
        size_response=tracker.get_slot("size_response")
        qty=tracker.get_slot("qty")
        order_qty_list=tracker.get_slot("order_qty_list")
        order_id_list=tracker.get_slot("order_id_list")
        item_in_list=tracker.get_slot("item_in_list")
        item_has_size=tracker.get_slot("item_has_size")
        same_item=tracker.get_slot("same_item")
        custom_ingtype1=tracker.get_slot("custom_ingtype1")
        custom_ingtype2=tracker.get_slot("custom_ingtype2")
        custom_ingtype3=tracker.get_slot("custom_ingtype3")
        custom_ingtype4=tracker.get_slot("custom_ingtype4")
        custom_ingtype5=tracker.get_slot("custom_ingtype5")
        customize=tracker.get_slot("customize")
        deliver_type=tracker.get_slot("deliver_type")
        currentQuery = tracker.get_slot("CurrentItems")
        if item==None:item=[]
        if (size==None or size ==[]):size =[None]
        if ((item_has_size == True) and (size_response)): size[0]=size_response
#        print("Order List, Order Qty Before:",order_id_list,order_qty_list)
        print("Order Action Before:",item,size,qty,order_id_list,order_qty_list)
        print("Customize in Order Action:",customize)
        if item:
           if ((len(size)==0) or ((len(size)>0) and (size[0]==[] or size[0]==None))):
              sql = "Select item_name,size,price,item_id,screen_id,ingtype1,ingtype2,ingtype3,ingtype4,ingtype5 from mipmenuitems where item_name = %s"
              choice = (item[0],)
           else:
              sql = "Select item_name,size,price,item_id,screen_id,ingtype1,ingtype2,ingtype3,ingtype4,ingtype5 from mipmenuitems where item_name = %s AND size = %s"
              choice = (item[0],size[0])
           mycursor.execute(sql,choice)
           myresult = mycursor.fetchall()
           print("Order Action Later:",item,size,qty,order_id_list,order_qty_list)
           if (mycursor.rowcount != 1):
              if (mycursor.rowcount > 1): # Item has size, received valid item but size not recognized as a valid size entity by NLU
                 dispatcher.utter_message("That is not a valid size for {}. Please restate your order of {}".format(item[0],item[0]))
                 if (same_item == False): del customize[len(custom_ingtype1)-1],custom_ingtype1[-1],custom_ingtype2[-1],custom_ingtype3[-1],custom_ingtype4[-1],custom_ingtype5[-1],order_qty_list[-1]
              elif ((len(size)==0) or ((len(size)>0) and size[0]==None)): # item has size, item incorrect and size not provided or wrong size provided
                 dispatcher.utter_message("Please restate your order with a valid item name and size".format())
              elif (len(size)!=0): # size is invalid but NLU has recognized the entity as size
                 dispatcher.utter_message("That is not a valid size for {}. Please restate your order of {}".format(item[0],item[0]))
              else: # item has size, size provided is right but item provided was incorrect
                 dispatcher.utter_message("There are no items on our menu that match {}. To know whats on our menu, say MENU".format(item[0]))
           else:
              for w,x,y,z,v,p,q,r,s,t in myresult:
                 if (item_has_size == True and same_item == False):
                    order_id_list.append(z) #if item is without size or size was provided in first order statement,order_id_list was already appended in find item
                    customize.append("")
                 if (same_item == False): dispatcher.utter_message("I have added {} {} size {} to your cart".format(order_qty_list[-1],x,w))
                 else:
                    if (len(qty)!=0): dispatcher.utter_message("I have added {} {} size {} to your cart".format(qty[0],x,w))
                    else: dispatcher.utter_message("I have added 1 {} size {} to your cart".format(x,w))
                 l=len(order_qty_list)
                 if (customize[l-1] != "" and same_item==False): dispatcher.utter_message("Also I have {} in your order of {}".format(customize[l-1],w))
#                 print("Order List,Order Qty Value Later:",order_id_list,order_qty_list)
                 item_has_size = False
           item = item[1:]
           qty = qty[1:]
           if size: size = size[1:]
           if item==[] and (order_id_list != []):
              currentQuery = None
              dispatcher.utter_message("You can ask me for anything else or say CHECKOUT".format())
              item_in_list = False
              size,qty=[],[]
        if (deliver_type is None): deliver_type="unassigned"
        return[SlotSet("order_id_list",order_id_list),SlotSet("deliver_type",deliver_type),SlotSet("item",item),SlotSet("size",size),SlotSet("qty",qty),SlotSet("order_qty_list",order_qty_list),SlotSet("item_has_size",item_has_size),SlotSet("item_in_list",item_in_list),SlotSet("size_response",None),SlotSet("custom_ingtype1",custom_ingtype1),SlotSet("custom_ingtype2",custom_ingtype2),SlotSet("custom_ingtype3",custom_ingtype3),SlotSet("custom_ingtype4",custom_ingtype4),SlotSet("custom_ingtype5",custom_ingtype5),SlotSet("customize",customize),SlotSet("CurrentItems",currentQuery)]

class RemoveItemAction(Action):
    def name(self) -> Text:
        return "remove_item_action"
    def run(self,dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        order_id_list=tracker.get_slot("order_id_list")
        order_qty_list=tracker.get_slot("order_qty_list")
        custom_ingtype1=tracker.get_slot("custom_ingtype1")
        custom_ingtype2=tracker.get_slot("custom_ingtype2")
        custom_ingtype3=tracker.get_slot("custom_ingtype3")
        custom_ingtype4=tracker.get_slot("custom_ingtype4")
        custom_ingtype5=tracker.get_slot("custom_ingtype5")
        customize=tracker.get_slot("customize")
        ingtype1_remove, ingtype2_remove, ingtype3_remove, ingtype4_remove, ingtype5_remove = [],[],[],[],[]
#        for i in range(5):
#           removevar = locals()['ingtype'+str(i+1)+'_remove']
#           removevar.append(next(tracker.get_latest_entity_values(entity_type='ing_type'+str(i+1),entity_role="exclude"),None))
        ingtype1_remove.append(next(tracker.get_latest_entity_values(entity_type="ing_type1"),None))
        ingtype2_remove.append(next(tracker.get_latest_entity_values(entity_type="ing_type2"),None))
        ingtype3_remove.append(next(tracker.get_latest_entity_values(entity_type="ing_type3"),None))
        ingtype4_remove.append(next(tracker.get_latest_entity_values(entity_type="ing_type4"),None))
        ingtype5_remove.append(next(tracker.get_latest_entity_values(entity_type="ing_type5"),None))
#        index1=len(custom_ingtype1)-1
        item=tracker.get_slot("item")
        index=tracker.get_slot("index")
        index_qty=tracker.get_slot("index_qty")
        print("Remove Item:",item,index,index_qty,order_id_list)
        if ((item) and (ingtype1_remove!=[None] or ingtype2_remove!=[None] or ingtype3_remove!=[None] or ingtype4_remove!=[None] or ingtype5_remove!=[None])):
           RemoveIngredientAction.run(self,dispatcher,tracker,domain)
        else:
           if (item and order_id_list):
              sql = "select item_id from mipmenuitems where item_name = %s"
              k = 0
              while k < len(item):
                 match_found=0
                 choice = (item[k],)
                 mycursor.execute(sql,choice)
                 myresult = mycursor.fetchall()
                 for j in range(mycursor.rowcount):
                    for i in order_id_list:
                       value = myresult[j]
                       if (value[0] == i):
                          index1 = order_id_list.index(i)
                          order_id_list.remove(i)
                          order_qty_list.pop(index1)
                          custom_ingtype1.pop(index1)
                          custom_ingtype2.pop(index1)
                          custom_ingtype3.pop(index1)
                          custom_ingtype4.pop(index1)
                          custom_ingtype5.pop(index1)
                          customize.pop(index1)
                          dispatcher.utter_message("Done! I have removed {} from your cart".format(item[k]))
                          match_found=1
                 if (match_found==0): dispatcher.utter_message("You do not have {} in your cart".format(item[k]))
                 k += 1
        if (index and order_id_list):
           if (order_id_list):
              len1 = len(order_id_list)
              if (index == "all"):
                 order_id_list,order_qty_list,custom_ingtype1,custom_ingtype2,custom_ingtype3,custom_ingtype4,custom_ingtype5,customize=[],[],[],[],[],[],[],[""]*20
                 dispatcher.utter_message("I have removed all items from your cart".format())
              elif (index == "last"):
                 if (index_qty):
                    if (int(index_qty)>len1): dispatcher.utter_message("You do not have {} items in your cart. Please rephrase your request".format(index_qty))
                    else:
                       order_id_list = order_id_list[:len(order_id_list)-int(index_qty)]
                       order_qty_list = order_qty_list[:len(order_qty_list)-int(index_qty)]
                       custom_ingtype1 = custom_ingtype1[:len(custom_ingtype1)-int(index_qty)]
                       custom_ingtype2 = custom_ingtype2[:len(custom_ingtype2)-int(index_qty)]
                       custom_ingtype3 = custom_ingtype3[:len(custom_ingtype3)-int(index_qty)]
                       custom_ingtype4 = custom_ingtype4[:len(custom_ingtype4)-int(index_qty)]
                       custom_ingtype5 = custom_ingtype5[:len(custom_ingtype5)-int(index_qty)]
                       customize = customize[:len1-int(index_qty)]
                       dispatcher.utter_message("Done! I have removed the last {} items from your cart".format(index_qty))
                 else:
                    del order_id_list[-1], order_qty_list[-1], custom_ingtype1[-1], custom_ingtype2[-1], custom_ingtype3[-1], custom_ingtype4[-1], custom_ingtype5[-1]
                    customize = customize[:len1-1]
                    dispatcher.utter_message("Done! I have removed the last item from your cart".format())
              elif (index == "first"):
                 if (index_qty):
                    if (int(index_qty)>len1): dispatcher.utter_message("You do not have {} items in your cart. Please rephrase your request".format(index_qty))
                    else:
                       del order_id_list[:int(index_qty)], order_qty_list[:int(index_qty)], custom_ingtype1[:int(index_qty)], custom_ingtype2[:int(index_qty)], custom_ingtype3[:int(index_qty)], custom_ingtype4[:int(index_qty)], custom_ingtype5[:int(index_qty)], customize[:int(index_qty)]
                       dispatcher.utter_message("Done! I have removed the first {} items from your cart".format(index_qty))
                 else:
                    del order_id_list[0], order_qty_list[0], custom_ingtype1[0], custom_ingtype2[0], custom_ingtype3[0], custom_ingtype4[0], custom_ingtype5[0], customize[0]
                    dispatcher.utter_message("Done! I have removed the first item from your cart".format())
           dispatcher.utter_message("You can ask me for anything else or say CHECKOUT".format())
        return[SlotSet("order_id_list",order_id_list),SlotSet("order_qty_list",order_qty_list),SlotSet("index",""),SlotSet("index_qty",""),SlotSet("item",""),SlotSet("custom_ingtype1",custom_ingtype1),SlotSet("custom_ingtype2",custom_ingtype2),SlotSet("custom_ingtype3",custom_ingtype3),SlotSet("custom_ingtype4",custom_ingtype4),SlotSet("custom_ingtype5",custom_ingtype5),SlotSet("customize",customize)]

class ChangeQtyAction(Action):
    def name(self) -> Text:
        return "change_qty_action"
    def run(self,dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        item=tracker.get_slot("item")
        qty=tracker.get_slot("qty")
        order_id_list=tracker.get_slot("order_id_list")
        order_qty_list=tracker.get_slot("order_qty_list")
        custom_ingtype1=tracker.get_slot("custom_ingtype1")
        custom_ingtype2=tracker.get_slot("custom_ingtype2")
        custom_ingtype3=tracker.get_slot("custom_ingtype3")
        custom_ingtype4=tracker.get_slot("custom_ingtype4")
        custom_ingtype5=tracker.get_slot("custom_ingtype5")
        if item == None: item = []
        if qty == None: qty = []
        print("Change Qty:",item,qty,order_id_list,order_qty_list)
        if ((len(item)==0) or (item==[]) or (len(qty)==0) or (qty==[])):
           dispatcher.utter_message("Please rephrase your change request with a valid item name and quantity that you want for the item")
        else:
           sql = "select item_id from mipmenuitems where item_name = %s"
           k = 0
           while k < len(item):
               match_found=0
               choice = (item[k],)
               mycursor.execute(sql,choice)
               myresult = mycursor.fetchall()
               for j in range(mycursor.rowcount):
                   for i in order_id_list:
                       value = myresult[j]
                       if (value[0] == i):
                           index = order_id_list.index(i)
                           order_qty_list[index]=qty[k]
                           dispatcher.utter_message("Done! I have changed the quantity of {} to {}".format(item[k],qty[k]))
                           match_found=1
               if (match_found==0): dispatcher.utter_message("You do not have {} in your cart".format(item[k]))
               k += 1
           dispatcher.utter_message("You can ask me for anything else or say CHECKOUT".format())
        return[SlotSet("order_id_list",order_id_list),SlotSet("order_qty_list",order_qty_list),SlotSet("item",""),SlotSet("qty","")]

class ChangeSizeAction(Action):
    def name(self) -> Text:
        return "change_size_action"
    def run(self,dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        item=tracker.get_slot("item")
        size=tracker.get_slot("size")
        order_id_list=tracker.get_slot("order_id_list")
        order_qty_list=tracker.get_slot("order_qty_list")
        custom_ingtype1=tracker.get_slot("custom_ingtype1")
        custom_ingtype2=tracker.get_slot("custom_ingtype2")
        custom_ingtype3=tracker.get_slot("custom_ingtype3")
        custom_ingtype4=tracker.get_slot("custom_ingtype4")
        custom_ingtype5=tracker.get_slot("custom_ingtype5")
        if item == None: item = []
        if size == None: size = []
        print("Change Size:",item,size,order_id_list,order_qty_list)
        if ((len(item)==0) or (item==[]) or (len(size)==0) or (size==[])):
           dispatcher.utter_message("Please rephrase your change request with a valid item name and size that you want for the item")
        else:
           sql = "select item_id from mipmenuitems where item_name = %s"
           k = 0
           while k < len(item):
              order_id_iter = list(order_id_list)
              match_found=0
              choice = (item[k],)
              mycursor.execute(sql,choice)
              myresult = mycursor.fetchall()
              item_match_found=0
              for j in range(mycursor.rowcount):
                 for i in order_id_iter:
                    value = myresult[j]
                    if (value[0] == i):
                       sql1 = "select item_id from mipmenuitems where item_name = %s and size = %s"
                       choice1 = (item[k],size[k])
                       mycursor.execute(sql1,choice1)
                       myresult1 = mycursor.fetchone()
                       item_match_found=1
                       if (myresult1):
                          index1 = order_id_list.index(i)
                          order_id_list[index1]=myresult1[0]
                          dispatcher.utter_message("Done! I have changed the size of {} to {}".format(item[k],size[k]))
                       else: dispatcher.utter_message("{} size {} is not available on our menu".format(size[k],item[k]))
              if (item_match_found==0): dispatcher.utter_message("You do not have {} in your cart".format(item[k]))
              k += 1
           dispatcher.utter_message("You can ask me for anything else or say CHECKOUT".format())
        return[SlotSet("order_id_list",order_id_list),SlotSet("order_qty_list",order_qty_list),SlotSet("item",""),SlotSet("size","")]

class RemoveIngredientAction(Action):
    def name(self) -> Text:
        return "remove_ingredient_action"
    def remove(ing_list,custom_ing,customize,index1,item,dispatcher:CollectingDispatcher):
        print("remove function: ing_list,custom_ing,item,index",ing_list,custom_ing,item,index1)
        for j in ing_list:
           ing_found = False
#           print(custom_ing[index1])
           if ("rem" in custom_ing[index1]):
               if (custom_ing[index1]["rem"]):
                  for i in custom_ing[index1]["rem"]:
                     if j.lower() == i.lower():
                        custom_ing[index1]["rem"].remove(i)
                        if "add" not in custom_ing[index1]: custom_ing[index1]["add"]= [i]
                        else: custom_ing[index1]["add"].append(i)
                        if "sto" not in custom_ing[index1]:custom_ing[index1]["sto"]= [i]
                        else: custom_ing[index1]["sto"].append(i)
                        custom_ing[index1]["sfr"] = custom_ing[index1]["rem"]
                        if(index1>=len(customize)):customize.append("")
                        customize[index1] += ("Removed " + str(i) + ",")
                        ing_found = True
           if ing_found == False: dispatcher.utter_message("You cannot remove {} from your order of {}".format(j,item))
#        print("customize in remove ingredient",customize)
        return (customize,custom_ing,ing_found)
    def run(self,dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
#        print("")
        item=tracker.get_slot("item")
#        print("item value in remove ingedient",item)
        entity_value=tracker.latest_message["entities"]
        newItem=CurrentItem()
        if item: newItem.set_query(entity_value,item,'remove_ing')
        ing_found=False
        custom_ingtype1=tracker.get_slot("custom_ingtype1")
        custom_ingtype2=tracker.get_slot("custom_ingtype2")
        custom_ingtype3=tracker.get_slot("custom_ingtype3")
        custom_ingtype4=tracker.get_slot("custom_ingtype4")
        custom_ingtype5=tracker.get_slot("custom_ingtype5")
        customize=tracker.get_slot("customize")
        if customize==None: customize = [""]*20
        order_id_list=tracker.get_slot("order_id_list")
        order_qty_list=tracker.get_slot("order_qty_list")
        index1=None
        print("Remove Ingredient:",item,order_id_list,order_qty_list)
        if order_id_list is None: dispatcher.utter_message("You do not have any items in your cart that can be modified".format())
        else:
           if (item):
              sql = "select item_id from mipmenuitems where item_name = %s"
              for k in range(len(item)):
                 match_found=0
                 choice = (item[k],)
                 mycursor.execute(sql,choice)
                 myresult = mycursor.fetchall()
                 for j in range(mycursor.rowcount):
                    for i in order_id_list:
                       value = myresult[j]
                       if (value[0] == i):
                          index1 = order_id_list.index(i)
                          match_found=1
                 if (match_found==0): dispatcher.utter_message("You do not have {} in your cart".format(item[k]))
                 elif (newItem.itemList[k]['name']==item[k]):
                    for ingv in range(len((newItem.itemList[k])['cust'])):
                        if (newItem.itemList[k]['cust'][ingv]['entity'])=='ing_type1': cust_ing_type=custom_ingtype1
                        elif (newItem.itemList[k]['cust'][ingv]['entity'])=='ing_type2': cust_ing_type=custom_ingtype2
                        elif (newItem.itemList[k]['cust'][ingv]['entity'])=='ing_type3': cust_ing_type=custom_ingtype3
                        elif (newItem.itemList[k]['cust'][ingv]['entity'])=='ing_type4': cust_ing_type=custom_ingtype4
                        elif (newItem.itemList[k]['cust'][ingv]['entity'])=='ing_type5': cust_ing_type=custom_ingtype5
                        if (newItem.itemList[k]['cust'][ingv]['role']=='exclude'):
                           customize,custom_ingtype1,ing_found=RemoveIngredientAction.remove([newItem.itemList[k]['cust'][ingv]['name']],cust_ing_type,customize,index1,item[k],dispatcher)
                           if(ing_found==True):dispatcher.utter_message("Done! I have removed {} from {}".format(newItem.itemList[k]['cust'][ingv]['name'],item[k]))
#                 if(ing_found==True):dispatcher.utter_message("Done! I have {} from {}".format(customize[k],item[k]))
        return[SlotSet("item",""),SlotSet("customize",customize),SlotSet("custom_ingtype1",custom_ingtype1),SlotSet("custom_ingtype2",custom_ingtype2),SlotSet("custom_ingtype3",custom_ingtype3),SlotSet("custom_ingtype4",custom_ingtype4),SlotSet("custom_ingtype5",custom_ingtype5)]

class AddIngredientAction(Action):
    def name(self) -> Text:
        return "add_ingredient_action"
    def add(ing_list,custom_ing,customize,index1,item,dispatcher:CollectingDispatcher):
#        print("")
        print("add function: ing_list,custom_ing,item,index",ing_list,custom_ing,item,index1)
        for j in ing_list:
           ing_found = False
           if ("add" in custom_ing[index1]):
               if (custom_ing[index1]["add"]):
                   for i in custom_ing[index1]["add"]:
                      if j.lower() == i.lower():
                         custom_ing[index1]["add"].remove(i)
                         if "rem" not in custom_ing[index1]: custom_ing[index1]["rem"]= [i]
                         else: custom_ing[index1]["rem"].append(i)
                         if "sfr" not in custom_ing[index1]: custom_ing[index1]["sfr"]= [i]
                         else: custom_ing[index1]["sfr"].append(i)
                         custom_ing[index1]["sto"]= custom_ing[index1]["add"]
                         if(index1>=len(customize)):customize.append("")
                         customize[index1] += ("Added " + str(i) + ",")
                         ing_found = True
           if ing_found == False: dispatcher.utter_message("You cannot add {} to your order of {}".format(j,item))
        return (customize,custom_ing,ing_found)
    def run(self,dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
#        print("")
        item=tracker.get_slot("item")
#        print("item value in add ingedient",item)
        entity_value=tracker.latest_message["entities"]
        newItem=CurrentItem()
        if item: newItem.set_query(entity_value,item,'add_ing')
        ing_found=False
        custom_ingtype1=tracker.get_slot("custom_ingtype1")
        custom_ingtype2=tracker.get_slot("custom_ingtype2")
        custom_ingtype3=tracker.get_slot("custom_ingtype3")
        custom_ingtype4=tracker.get_slot("custom_ingtype4")
        custom_ingtype5=tracker.get_slot("custom_ingtype5")
        customize=tracker.get_slot("customize")
        if customize==None: customize = [""]*20
        order_id_list=tracker.get_slot("order_id_list")
        order_qty_list=tracker.get_slot("order_qty_list")
        index1=None
        print("Add Ingredient:",item,order_id_list,order_qty_list)
        if order_id_list is None: dispatcher.utter_message("You do not have any items in your cart that can be modified".format())
        else:
           if (item):
              sql = "select item_id from mipmenuitems where item_name = %s"
              k = 0
              for k in range(len(item)):
                 match_found=0
                 choice = (item[k],)
                 mycursor.execute(sql,choice)
                 myresult = mycursor.fetchall()
                 for j in range(mycursor.rowcount):
                    for i in order_id_list:
                       value = myresult[j]
                       if (value[0] == i):
                          index1 = order_id_list.index(i)
                          match_found=1
                 if (match_found==0): dispatcher.utter_message("You do not have {} in your cart".format(item[k]))
                 elif (newItem.itemList[k]['name']==item[k]):
                    for ingv in range(len((newItem.itemList[k])['cust'])):
                       if (newItem.itemList[k]['cust'][ingv]['entity'])=='ing_type1': cust_ing_type=custom_ingtype1
                       elif (newItem.itemList[k]['cust'][ingv]['entity'])=='ing_type2': cust_ing_type=custom_ingtype2
                       elif (newItem.itemList[k]['cust'][ingv]['entity'])=='ing_type3': cust_ing_type=custom_ingtype3
                       elif (newItem.itemList[k]['cust'][ingv]['entity'])=='ing_type4': cust_ing_type=custom_ingtype4
                       elif (newItem.itemList[k]['cust'][ingv]['entity'])=='ing_type5': cust_ing_type=custom_ingtype5
                       if (newItem.itemList[k]['cust'][ingv]['role']=='include'):
                          customize,custom_ingtype1,ing_found=AddIngredientAction.add([newItem.itemList[k]['cust'][ingv]['name']],cust_ing_type,customize,index1,item[k],dispatcher)
                          if (ing_found==True): dispatcher.utter_message("Done! I have added {} to {}".format(newItem.itemList[k]['cust'][ingv]['name'],item[k]))
        return[SlotSet("item",""),SlotSet("customize",customize),SlotSet("custom_ingtype1",custom_ingtype1),SlotSet("custom_ingtype2",custom_ingtype2),SlotSet("custom_ingtype3",custom_ingtype3),SlotSet("custom_ingtype4",custom_ingtype4),SlotSet("custom_ingtype5",custom_ingtype5)]

class SubstituteIngredientAction(Action):
    def name(self) -> Text:
        return "substitute_ingredient_action"
    def substitute(ing_from,ing_to,custom_ing,customize,index1,item,dispatcher:CollectingDispatcher):
#        print("")
        print("substitute function: ing_list,custom_ing,item,index",ing_list,custom_ing,item,index1)
        ing_found = False
        if ((ing_from != []) and (ing_from != [None]) and (ing_to != []) and (ing_to != [None])):
           if ("sfr" in custom_ing[index1]) and ("sto" in custom_ing[index1]):
              ing_found = False
              for i in custom_ing[index1]["sfr"]:
#                 print("value of i:",i)
                 if (ing_from[0].lower() == i.lower()):
                    for j in custom_ing[index1]["sto"]:
#                       print("i and j:",i,j)
#                       print(ing_to[0],j)
                       if (ing_to[0].lower() == j.lower()):
                          custom_ing[index1]["sfr"].remove(i)
                          custom_ing[index1]["sto"].append(i)
                          custom_ing[index1]["sto"].remove(j)
                          custom_ing[index1]["sfr"].append(j)
                          if ("rem" in custom_ing[index1]):
                             custom_ing[index1]["rem"].remove(i)
                             custom_ing[index1]["rem"].append(j)
                          if ("add" in custom_ing[index1]):
                             custom_ing[index1]["add"].remove(j)
                             custom_ing[index1]["add"].append(i)
                          ing_found = True
                          if(index1>=len(customize)):customize.append("")
                          customize[index1] += ("Replaced " + str(i) + " With " + str(j) + ",")
           if (ing_found == False): dispatcher.utter_message("You cannot replace {} with {} in your order of {}".format(ing_from[0],ing_to[0],item))
        return(customize,custom_ing,ing_found)
    def run(self,dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
#        print("")
        item=tracker.get_slot("item")
#        print("item value in add ingedient",item)
        entity_value=tracker.latest_message["entities"]
        newItem=CurrentItem()
        if item: newItem.set_query(entity_value,item,'replace_ing')
        ing_found=False
        custom_ingtype1=tracker.get_slot("custom_ingtype1")
        custom_ingtype2=tracker.get_slot("custom_ingtype2")
        custom_ingtype3=tracker.get_slot("custom_ingtype3")
        custom_ingtype4=tracker.get_slot("custom_ingtype4")
        custom_ingtype5=tracker.get_slot("custom_ingtype5")
        customize=tracker.get_slot("customize")
        order_id_list=tracker.get_slot("order_id_list")
        order_qty_list=tracker.get_slot("order_qty_list")
        if customize==None: customize = [""]*20
        index1=0
        print("Substitute Ingredient:",item,order_id_list,order_qty_list)
        if order_id_list is None:
            dispatcher.utter_message("You do not have any items in your cart that can be modified".format())
        else:
           if (item):
              sql = "select item_id from mipmenuitems where item_name = %s"
              k = 0
              for k in range(len(item)):
                 match_found=0
                 choice = (item[k],)
                 mycursor.execute(sql,choice)
                 myresult = mycursor.fetchall()
                 for j in range(mycursor.rowcount):
                    for i in order_id_list:
                       value = myresult[j]
                       if (value[0] == i):
                          index1 = order_id_list.index(i)
                          match_found=1
                 if (match_found==0): dispatcher.utter_message("You do not have {} in your cart".format(item[k]))
                 elif (newItem.itemList[k]['name']==item[k]):
                    for ingv in range(len((newItem.itemList[k])['cust'])):
                       if (newItem.itemList[k]['cust'][ingv]['entity'])=='ing_type1': cust_ing_type=custom_ingtype1
                       elif (newItem.itemList[k]['cust'][ingv]['entity'])=='ing_type2': cust_ing_type=custom_ingtype2
                       elif (newItem.itemList[k]['cust'][ingv]['entity'])=='ing_type3': cust_ing_type=custom_ingtype3
                       elif (newItem.itemList[k]['cust'][ingv]['entity'])=='ing_type4': cust_ing_type=custom_ingtype4
                       elif (newItem.itemList[k]['cust'][ingv]['entity'])=='ing_type5': cust_ing_type=custom_ingtype5
                       if (newItem.itemList[k]['cust'][ingv]['role']=='from'):
                          itmfrom =  next(iter((newItem.itemList[k]['cust'][ingv]['name']).keys()))
                          itmto = next(iter((newItem.itemList[k]['cust'][ingv]['name']).values()))
                          customize,custom_ingtype1,ing_found=SubstituteIngredientAction.substitute([itmfrom],[itmto],cust_ing_type,customize,index1,item[k],dispatcher)
                          if(ing_found==True):dispatcher.utter_message("Done! I have replaced {} with {} in {}".format(itmfrom,itmto,item[k]))
        return[SlotSet("item",""),SlotSet("customize",customize),SlotSet("custom_ingtype1",custom_ingtype1),SlotSet("custom_ingtype2",custom_ingtype2),SlotSet("custom_ingtype3",custom_ingtype3),SlotSet("custom_ingtype4",custom_ingtype4),SlotSet("custom_ingtype5",custom_ingtype5)]

class ShowCartAction(Action):
    def name(self) -> Text:
        return "show_cart_action"
    def run(self,dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        order_id_list=tracker.get_slot("order_id_list")
        order_qty_list=tracker.get_slot("order_qty_list")
        custom_ingtype1=tracker.get_slot("custom_ingtype1")
        custom_ingtype2=tracker.get_slot("custom_ingtype2")
        custom_ingtype3=tracker.get_slot("custom_ingtype3")
        custom_ingtype4=tracker.get_slot("custom_ingtype4")
        custom_ingtype5=tracker.get_slot("custom_ingtype5")
        ShowCartAction.show(dispatcher,tracker,order_id_list,order_qty_list,custom_ingtype1,custom_ingtype2,custom_ingtype3,custom_ingtype4,custom_ingtype5)
        return[]
    def show(dispatcher: CollectingDispatcher,tracker: Tracker,order_id_list,order_qty_list,custom_ingtype1,custom_ingtype2,custom_ingtype3,custom_ingtype4,custom_ingtype5):
        customize=tracker.get_slot("customize")
        if (order_id_list):
           i,a=0,0
           print("Show Cart:",order_id_list,order_qty_list)
           dispatcher.utter_message("Your cart includes the following items".format())
           for id in order_id_list:
              sql = "Select item_name,size,price from mipmenuitems where item_id = %s"
              choice = (id,)
              mycursor.execute(sql,choice)
              myresult = mycursor.fetchall()
              cust_text = customize[i]
              cust_price_list,cust_text_list=[],[]
              cust_string_from, cust_string_to = "",""
              if "Added" in cust_text or "Removed" in cust_text or "Replaced" in cust_text:
                 cust_text_list=cust_text.split(",")
                 for element in cust_text_list:
                     if element == '':cust_text_list.remove(element)
                 for j in cust_text_list:
                    cust_string=""
                    if "Added" in j:
                        cust_item=j.replace("Added ","").strip(",")
                        sql1 = "Select ing_price from mipingprice where ing_name = %s"
                        choice1=(cust_item,)
                        mycursor.execute(sql1,choice1)
                        myresult1 = mycursor.fetchone()
                        if myresult1: cust_string = json.loads(myresult1[0])
                        for x,y,z in myresult:
                           if y in (cust_string): cust_price_list.append('$'+cust_string[y])
                    elif "Replaced" in j:
                        cust_item=j.replace("Replaced ","").strip(",").replace(" With ",",").split(",")
                        m=0
                        for c in cust_item:
                           sql2 = "select ing_price from mipingprice where ing_name = %s"
                           choice2=(c,)
                           mycursor.execute(sql2,choice2)
                           myresult2 = mycursor.fetchone()
                           if myresult2 and m==0: cust_string_from = json.loads(myresult2[0])
                           if myresult2 and m==1: cust_string_to = json.loads(myresult2[0])
                           m=m+1
                        for x,y,z in myresult:
                           if y in (cust_string_from): cust_string_from=cust_string_from[y]
                           if y in (cust_string_to): cust_string_to=cust_string_to[y]
                           cust_price_calc = float(cust_string_to) - float(cust_string_from)
                           cust_price_list.append('$'+str(cust_price_calc))
                    elif "Removed" in j:
                           cust_price_list.append('$0.0')
              for x,y,z in myresult:
                 if i < len(order_qty_list):
                    a=int(order_qty_list[i])*z
                    dispatcher.utter_message("{} {} size {}".format(order_qty_list[i],y,x))
                    j=0
                    for cust in cust_text_list:
                       dispatcher.utter_message("  {}".format(cust_text_list[j]))
                       j=j+1
                    i=i+1
           dispatcher.utter_message("You can ask me for anything else or say CHECKOUT".format())
        else: dispatcher.utter_message("There are no items in your cart. What would you like to order?".format())
        return[]

class CheckoutAction(Action):
    def name(self) -> Text:
        return "checkout_action"
    def run(self,dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        order_id_list=tracker.get_slot("order_id_list")
        order_qty_list=tracker.get_slot("order_qty_list")
        custom_ingtype1=tracker.get_slot("custom_ingtype1")
        custom_ingtype2=tracker.get_slot("custom_ingtype2")
        custom_ingtype3=tracker.get_slot("custom_ingtype3")
        custom_ingtype4=tracker.get_slot("custom_ingtype4")
        custom_ingtype5=tracker.get_slot("custom_ingtype5")
        customize=tracker.get_slot("customize")
        order_no = 0
        print("Checkout Action:",order_id_list,order_qty_list)
        if customize==None:customize=[]
        total=0
        if (order_id_list):
           i=0
           sql1 = "select order_id from miporderbook order by order_id desc limit 1"
           mycursor.execute(sql1)
           result1 = mycursor.fetchone()
           if (result1): order_no = int(result1[0]) + 1
           else: order_no = 1001
           dispatcher.utter_message("Here is your order list for checkout".format())
           for id in order_id_list:
              sql = "Select item_name,size,price from mipmenuitems where item_id = %s"
              choice = (id,)
              mycursor.execute(sql,choice)
              myresult = mycursor.fetchall()
              cust_text = customize[i]
              cust_price_list,cust_text_list=[],[]
              cust_string_from, cust_string_to = "",""
              if "Added" in cust_text or "Removed" in cust_text or "Replaced" in cust_text:
                 cust_text_list=cust_text.split(",")
                 for element in cust_text_list:
                     if element == '':cust_text_list.remove(element)
                 for j in cust_text_list:
                    cust_string=""
                    if "Added" in j:
                        cust_item=j.replace("Added ","").strip(",")
                        sql1 = "Select ing_price from mipingprice where ing_name = %s"
                        choice1=(cust_item,)
                        mycursor.execute(sql1,choice1)
                        myresult1 = mycursor.fetchone()
                        if myresult1: cust_string = json.loads(myresult1[0])
                        for x,y,z in myresult:
                           if y in (cust_string): cust_price_list.append('$'+cust_string[y])
                    elif "Replaced" in j:
                        cust_item=j.replace("Replaced ","").strip(",").replace(" With ",",").split(",")
                        m=0
                        for c in cust_item:
                           sql2 = "select ing_price from mipingprice where ing_name = %s"
                           choice2=(c,)
                           mycursor.execute(sql2,choice2)
                           myresult2 = mycursor.fetchone()
                           if myresult2 and m==0: cust_string_from = json.loads(myresult2[0])
                           if myresult2 and m==1: cust_string_to = json.loads(myresult2[0])
                           m=m+1
                        for x,y,z in myresult:
                           if y in (cust_string_from): cust_string_from=cust_string_from[y]
                           if y in (cust_string_to): cust_string_to=cust_string_to[y]
                           cust_price_calc = float(cust_string_to) - float(cust_string_from)
                           cust_price_list.append('$'+str(cust_price_calc))
                    elif "Removed" in j: cust_price_list.append('$0.0')
              for x,y,z in myresult:
                 a=int(order_qty_list[i])*z
                 dispatcher.utter_message("{} {} size {}".format(order_qty_list[i],y,x))
                 j=0
                 for cust in cust_text_list:
                    dispatcher.utter_message("  {}".format(cust_text_list[j]))
                    j=j+1
                 quantity=int(order_qty_list[i])
                 l,sum=0,0
                 while l < len(cust_price_list):
                    cust_price_list[l]=cust_price_list[l].replace("$","")
                    sum=sum+float(cust_price_list[l])
                    l+=1
                 total = float(total)+float(z)*float(quantity)+sum*quantity
                 total = str(round(total,2))
                 sql2 = "Insert into miporderbook (order_id, item_id, item_name, size, ingtype1, ingtype2, ingtype3, ingtype4, ingtype5, customize, qty, price, value, total) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                 col_values = (order_no,id,x,y,json.dumps(custom_ingtype1[i]),json.dumps(custom_ingtype2[i]),json.dumps(custom_ingtype3[i]),json.dumps(custom_ingtype4[i]),json.dumps(custom_ingtype5[i]),customize[i],order_qty_list[i],z,a,total)
                 mycursor.execute(sql2,col_values)
              i=i+1
           Tax = float(total) * 0.09
           Fee = float(total) * 0.0399
           totAmount1 = round((float(total) + Tax + Fee),2)
           dispatcher.utter_message("Your total amount including taxes and fees is ${}".format(totAmount1))
           cnx.commit()
           dispatcher.utter_message("Please say or enter your ten digit phone number".format())
        else: dispatcher.utter_message("There are no items in your cart".format())
        return[SlotSet("order_no",order_no)]

class CheckCustomerTypeAction(Action):
    def name(self) -> Text:
        return "check_customer_type"
    def run(self,dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        order_id_list=tracker.get_slot("order_id_list")
        order_qty_list=tracker.get_slot("order_qty_list")
        order_no = tracker.get_slot("order_no")
        customize=tracker.get_slot("customize")
        custom_ingtype1=tracker.get_slot("custom_ingtype1")
        custom_ingtype2=tracker.get_slot("custom_ingtype2")
        custom_ingtype3=tracker.get_slot("custom_ingtype3")
        custom_ingtype4=tracker.get_slot("custom_ingtype4")
        custom_ingtype5=tracker.get_slot("custom_ingtype5")
        deliver_type=tracker.get_slot("deliver_type")
        current_customer=tracker.get_slot("current_customer")
        cust_response=tracker.get_slot("cust_response")
        phone=tracker.get_slot("phone")
        print("Check Customer Type",phone,order_id_list,order_qty_list)
        if order_id_list and order_no:
           sql = "Select street, city, state, zip from mipcustomerdetails where phone = %s"
           choice = (phone,)
           mycursor.execute(sql,choice)
           myresult = mycursor.fetchall()
           if myresult:
              current_customer = True
              value = myresult[0]
              if (deliver_type.lower() == "delivery"):
                 if (value[0] and value[1] and value[2] and value[3]):
                    cust_response="complete"
                    dispatcher.utter_message("We have your address on our records as {} in {}. Would you like to use the SAME ADDRESS for delivery or a DIFFERENT ADDRESS?".format(value[0],value[1]))
                 else: cust_response="incomplete" ## Checkout case 6: delivery option chosen, current customer but address not in database
           else: current_customer = False
           if (deliver_type.lower() == "pickup"): cust_response="incomplete"
           return[SlotSet("current_customer",current_customer),SlotSet("deliver_type",deliver_type),SlotSet("cust_response",cust_response)]
        else:
           if order_id_list:
              dispatcher.utter_message("I can only take your information once you are ready to checkout.To checkout say CHECKOUT or let me know what else you would like to order".format())
              return[AllSlotsReset(),SlotSet("current_customer",current_customer),SlotSet("deliver_type",deliver_type),SlotSet("cust_response",cust_response),SlotSet("order_id_list",order_id_list),SlotSet("order_qty_list",order_qty_list),SlotSet("order_no",order_no),SlotSet("customize",customize),SlotSet("custom_ingtype1",custom_ingtype1),SlotSet("custom_ingtype2",custom_ingtype2),SlotSet("custom_ingtype3",custom_ingtype3),SlotSet("custom_ingtype4",custom_ingtype4),SlotSet("custom_ingtype5",custom_ingtype5)]
           else:
              dispatcher.utter_message("I can only take your information once you have items in your cart and go for checkout. Let me know what you would like to order. To know whats on your menu, say MENU".format())
              return[AllSlotsReset(),SlotSet("current_customer",current_customer),SlotSet("deliver_type",deliver_type),SlotSet("cust_response",cust_response)]

class CustomerDetailsComplete(FormAction):
    def name(self):
        return "customer_details_complete"
    @staticmethod
    def required_slots(tracker: Tracker):
        return ["phone","street","city","state","zip"]
    def validate(self, dispatcher, tracker, domain):
        slot_values = self.extract_other_slots(dispatcher, tracker, domain)
        slot_to_fill = tracker.get_slot("requested_slot")
        if slot_to_fill:
           slot_values.update(self.extract_requested_slot(dispatcher, tracker, domain))
        for slot, value in slot_values.items():
           if slot == 'phone':
              if len(value) > 12 or re.match("^[\d-]*$",value) == False:
                 dispatcher.utter_template('utter_wrong_phone',tracker)
                 slot_values[slot] = None
           elif slot == 'street':
              if re.match("^[\w\d_-]*$",value.replace(" ",""))  == False:
                 dispatcher.utter_template('utter_wrong_street',tracker)
                 slot_values[slot] = None
           elif slot == 'city':
              if value.replace(" ","").isalpha() == False:
                 dispatcher.utter_template('utter_wrong_city',tracker)
                 slot_values[slot] = None
           elif slot == 'state':
              if value.replace(" ","").isalpha() == False:
                 dispatcher.utter_template('utter_wrong_state',tracker)
                 slot_values[slot] = None
           elif slot == 'zip':
              if len(value) != 5 or value.isdigit() == False:
                 dispatcher.utter_template('utter_wrong_zip',tracker)
                 slot_values[slot] = None
        return [SlotSet(slot, value) for slot, value in slot_values.items()]
    def submit(self, dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        order_no=tracker.get_slot("order_no")
        cust_response=tracker.get_slot("cust_response")
        deliver_type=tracker.get_slot("deliver_type")
        current_customer=tracker.get_slot("current_customer")
        phone=tracker.get_slot("phone")
        street=tracker.get_slot("street")
        city=tracker.get_slot("city")
        state=tracker.get_slot("state")
        zip=tracker.get_slot("zip")
        print("Customer Details Complete:",deliver_type,current_customer,cust_response)
## Checkout case 3: delivery option chosen and new customer
        if (current_customer == False):
           sql = "Insert into mipcustomerdetails (phone, street, city, state, zip) values (%s, %s, %s, %s, %s)"
           col = (phone,street,city,state,zip)
        else:
## Checkout case 4: delivery option chosen, existing customer, want delivery at different address
           sql = "Update mipcustomerdetails set street = %s, city = %s, state = %s, zip = %s where phone = %s"
           col = (street,city,state,zip,phone)
        mycursor.execute(sql,col)
        sql1 = "Update miporderbook set order_date = curdate(), order_time = curtime(), phone = %s where order_id = %s"
        col1 = (phone, order_no)
        mycursor.execute(sql1,col1)
        cnx.commit()
        return[SlotSet("zip",None),SlotSet("cust_response",None)]

class CustomerDetailsName(FormAction):
    def name(self):
        return "customer_details_name"
    @staticmethod
    def required_slots(tracker: Tracker):
        return ["phone"]
    def validate(self, dispatcher, tracker, domain):
        slot_values = self.extract_other_slots(dispatcher, tracker, domain)
        slot_to_fill = tracker.get_slot("requested_slot")
        if slot_to_fill: slot_values.update(self.extract_requested_slot(dispatcher, tracker, domain))
        for slot, value in slot_values.items():
           if slot == 'phone':
              if len(value) > 12 or re.match("^[\d-]*$",value) == False:
                 dispatcher.utter_template('utter_wrong_phone',tracker)
                 slot_values[slot] = None
        return [SlotSet(slot, value) for slot, value in slot_values.items()]
    def submit(self, dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        order_no=tracker.get_slot("order_no")
        deliver_type=tracker.get_slot("deliver_type")
        current_customer=tracker.get_slot("current_customer")
        cust_response=tracker.get_slot("cust_response")
        phone=tracker.get_slot("phone")
        print("Customer Details Name:",deliver_type,current_customer,cust_response)
        if (deliver_type.lower() == "pickup"):
           if (current_customer == False):
## Checkout case 1: pickup option chosen and new customer
              sql = "Insert into mipcustomerdetails (phone) values (%s)"
              col = (phone,)
              mycursor.execute(sql,col)
## Checkout case 2: pickup option chosen and current customer, no DB update required
#        elif (deliver_type.lower() == "delivery"):
## Checkout case 5: delivery option chosen and existing customer, wants same address for delivery, no DB update required
#           sql1 = "Select street,city from mipcustomerdetails where phone = %s"
#           col1 = (phone,)
#           mycursor.execute(sql1,col1)
#           myresult = mycursor.fetchall()
#           if myresult: value = myresult[0]
        sql2 = "Update miporderbook set order_date = curdate(), order_time = curtime(), phone = %s where order_id = %s"
        col2 = (phone, order_no)
        mycursor.execute(sql2,col2)
        cnx.commit()
        if (deliver_type.lower() == "pickup"):
           sendOrderEmail(order_no,phone)
           dispatcher.utter_message("Your order is confirmed and the order number is {}. It will be ready for pickup in 30 minutes. Have a nice day".format(order_no))           
           return[AllSlotsReset()]
        return[SlotSet("zip",None),SlotSet("cust_response",None)]

class CheckPaymentInfo(Action):
    def name(self) -> Text:
        return "check_payment_info"
    def run(self,dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        phone=tracker.get_slot("phone")
        cust_response=tracker.get_slot("cust_response")
        print("Check Payment Info",phone,cust_response)
        sql = "Select card_no,card_month,card_year,card_cvv,card_name,card_zip from mipcustomerdetails where phone = %s"
        choice = (phone,)
        mycursor.execute(sql,choice)
        myresult = mycursor.fetchone()
        if myresult:
           card_no = myresult[0]
           if card_no is not None:
              dispatcher.utter_message("We have your card ending in {} {} {} {} on our records. Would you like to use the same card or a different card".format(card_no[-4],card_no[-3],card_no[-2],card_no[-1]))
              current_customer = True
           else: current_customer = False
        else: current_customer = False
        return[SlotSet("current_customer",current_customer)]

class PaymentInfoComplete(FormAction):
    def name(self):
        return "payment_info_complete"
    @staticmethod
    def required_slots(tracker: Tracker):
        return ["card_no","card_month","card_year","card_cvv","card_name","zip"]
    def validate(self, dispatcher, tracker, domain):
        slot_values = self.extract_other_slots(dispatcher, tracker, domain)
        slot_to_fill = tracker.get_slot("requested_slot")
        if slot_to_fill: slot_values.update(self.extract_requested_slot(dispatcher, tracker, domain))
        for slot, value in slot_values.items():
           if slot == 'card_no':
              if len(value) not in range(15,17) or re.match("^[\d]*$",value) == False:
                 dispatcher.utter_template('utter_wrong_card_no',tracker)
                 slot_values[slot] = None
           if slot == 'card_month':
              if len(value) != 2 or re.match("^0[1-9]|1[0-2]$",value) == False:
                 dispatcher.utter_template('utter_wrong_card_month',tracker)
                 slot_values[slot] = None
           if slot == 'card_year':
              if len(value) != 2 or re.match("^[2-3][0-9]$",value) == False:
                 dispatcher.utter_template('utter_wrong_card_year',tracker)
                 slot_values[slot] = None
           elif slot == 'card_cvv':
              if len(value) not in range (3,5) or re.match("^[0-9]{3,4}$",value) == False:
                 dispatcher.utter_template('utter_wrong_card_cvv',tracker)
                 slot_values[slot] = None
           elif slot == 'card_name':
              if value.replace(" ","").isalpha() == False:
                 dispatcher.utter_template('utter_wrong_card_name',tracker)
                 slot_values[slot] = None
           elif slot == 'zip':
              if len(value) != 5 or value.isdigit() == False:
                 dispatcher.utter_template('utter_wrong_zip',tracker)
                 slot_values[slot] = None
        return [SlotSet(slot, value) for slot, value in slot_values.items()]
    def submit(self, dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        phone=tracker.get_slot("phone")
        street=tracker.get_slot("street")
        city=tracker.get_slot("city")
        order_no=tracker.get_slot("order_no")
        card_no=tracker.get_slot("card_no")
        card_month=tracker.get_slot("card_month")
        card_year=tracker.get_slot("card_year")
        card_cvv=tracker.get_slot("card_cvv")
        card_name=tracker.get_slot("card_name")
        zip=tracker.get_slot("zip")
        deliver_type=tracker.get_slot("deliver_type")
        current_customer=tracker.get_slot("current_customer")
        cust_response=tracker.get_slot("cust_response")
        print("Payment Info Complete:",deliver_type,current_customer,cust_response)
        sql = "Update mipcustomerdetails set card_no = %s, card_month = %s, card_year = %s, card_cvv = %s, card_name = %s, card_zip = %s where phone = %s"
        col = (card_no,card_month,card_year,card_cvv,card_name,zip,phone)
        mycursor.execute(sql,col)
        if (deliver_type.lower()=="delivery"): dispatcher.utter_message("Your order is confirmed and the order number is {}. It will be delivered to {} in {} within 45 to 60 minutes. Have a nice day".format(order_no,street,city))
        else: dispatcher.utter_message("Your order is confirmed and the order number is {}. It will be ready for pickup in 30 minutes. Have a nice day".format(order_no))
        sendOrderEmail(order_no,phone)
        cnx.commit()
        return[AllSlotsReset()]

def sendOrderEmail(order_no,phone):
   sql = "select item_name,size,customize,qty,price,value,total from miporderbook where order_id = %s"
   choice = (order_no,)
   mycursor.execute(sql,choice)
   myresult=mycursor.fetchall()
   orderDet=[]
   for x,y,z,a,b,c,d in myresult:
#      print (x,y,z,a,b,c,d)
      itemDet={'name':x,'size':y,'customize':z,'qty':a}
      orderDet.append(itemDet)
      totAmount=str(d)
#   print(orderDet)
   SendEmailOrder.setEmailContent(orderDet,order_no,totAmount,phone)

class PaymentInfoShort(FormAction):
    def name(self):
        return "payment_info_short"
    @staticmethod
    def required_slots(tracker: Tracker):
        return ["card_cvv"]
    def submit(self, dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        phone=tracker.get_slot("phone")
        street=tracker.get_slot("street")
        city=tracker.get_slot("city")
        order_no=tracker.get_slot("order_no")
        card_cvv=tracker.get_slot("card_cvv")
        deliver_type=tracker.get_slot("deliver_type")
        current_customer=tracker.get_slot("current_customer")
        cust_response=tracker.get_slot("cust_response")
        print("Payment Info Short:",deliver_type,current_customer,cust_response)
        sql = "Update mipcustomerdetails set card_cvv = %s where phone = %s"
        col = (card_cvv,phone)
        mycursor.execute(sql,col)
        if (deliver_type.lower()=="delivery"): dispatcher.utter_message("Your order is confirmed and the order number is {}. It will be delivered to {} in {} within 45 to 60 minutes. Have a nice day".format(order_no,street,city))
        else: dispatcher.utter_message("Your order is confirmed and the order number is {}. It will be ready for pickup in 30 minutes. Have a nice day".format(order_no))
        sendOrderEmail(order_no,phone)
        return[AllSlotsReset()]

class ShowIngredientAction(Action):
    def name(self)-> Text:
        return "show_ingredient_action"
    def run(self,dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        item = tracker.get_slot("item")
        category = tracker.get_slot("category")
        group = tracker.get_slot("group")
        subcategory = tracker.get_slot("subcategory")
        if item == None: item = []
        print("Show Ingredient:",item,category,group,subcategory)
        if (item or group or category or subcategory):
           if len(item) > 0:
              sql = "select item_name,item_contains from mipmenuitems where item_name = %s"
              choice = (item[0],)
              mycursor.execute(sql,choice)
              myresult = mycursor.fetchone()
              if myresult: dispatcher.utter_message("Our {} includes {}. To order any item say the item name. To know the items on our menu say MENU".format(myresult[0],myresult[1]))
              else: dispatcher.utter_message("There are no items on our menu that match {}. To know whats on our menu say MENU".format(item[0]))
              return[SlotSet("item",None)]
           else:
              if (group or category or subcategory):
                 showInfo(group,category,subcategory,dispatcher)
                 return[SlotSet("group",None),SlotSet("subcategory",None),SlotSet("category",None)]
        else:
           dispatcher.utter_message("There are no such items on our menu. To know whats on our menu, say MENU".format())
           return[]

class CustomizeItemAction(Action):
    def name(self) -> Text:
        return "customize_item_action"
    def run(self,dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        item =  tracker.get_slot("item")
        if item == None: item = []
        print("Customize Item:",item)
        if (len(item) > 0):
           sql = "select item_name,ingtype1,ingtype2,ingtype3,ingtype4,ingtype5 from mipmenuitems where item_name = %s"
           choice = (item[0],)
           mycursor.execute(sql,choice)
           myresult = mycursor.fetchone()
           if myresult:
              myresult1 = myresult[1:]
              add_str,rem_str = "",""
              for i in myresult1:
                 i = json.loads(i).copy()
                 if "add" in i: add_str = add_str + ', '.join(map(str, i["add"])) + ", "
                 if "rem" in i: rem_str = rem_str + ', '.join(map(str, i["rem"])) + ", "
              if (add_str=="" and rem_str==""):
                 dispatcher.utter_message("There are no modifications possible in {}".format(item[0]))
              else:
                 if (add_str != ""):dispatcher.utter_message("The following ingredients can be added to {}: {}".format(item[0],add_str))
                 if (rem_str != ""):dispatcher.utter_message("The following ingredients can be removed from {}: {}".format(item[0],rem_str))
           else:
              dispatcher.utter_message("Please restate your order with a valid item name.To know whats on our menu, say MENU".format())
        else:
           dispatcher.utter_message("There are no such items on our menu. To know whats on our menu, say MENU".format())
        return[SlotSet("item",None)]

class EditItemAction(Action):
    def name(self) -> Text:
        return "edit_item_action"
    def run(self,dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        item =  tracker.get_slot("item")
        order_id_list = tracker.get_slot("order_id_list")
        custom_ingtype1=tracker.get_slot("custom_ingtype1")
        custom_ingtype2=tracker.get_slot("custom_ingtype2")
        custom_ingtype3=tracker.get_slot("custom_ingtype3")
        custom_ingtype4=tracker.get_slot("custom_ingtype4")
        custom_ingtype5=tracker.get_slot("custom_ingtype5")
        if item == None: item = []
        print("Edit Item:",item,order_id_list)
        if (len(item) > 0):
           if (order_id_list):
               sql = "select item_id,size from mipmenuitems where item_name = %s"
               match_found=0
               choice = (item[0],)
               mycursor.execute(sql,choice)
               myresult = mycursor.fetchall()
               if myresult:
                  add_str, rem_str = "",""
                  for j in range(mycursor.rowcount):
                     for i in order_id_list:
                        if (myresult[j][0] == i):
                           index1 = order_id_list.index(i)
                           if "add" in custom_ingtype1[index1]: add_str = add_str + ', '.join(map(str, custom_ingtype1[index1]["add"])) + ", "
                           if "add" in custom_ingtype2[index1]: add_str = add_str + ', '.join(map(str, custom_ingtype2[index1]["add"])) + ", "
                           if "add" in custom_ingtype3[index1]: add_str = add_str + ', '.join(map(str, custom_ingtype3[index1]["add"])) + ", "
                           if "add" in custom_ingtype4[index1]: add_str = add_str + ', '.join(map(str, custom_ingtype4[index1]["add"])) + ", "
                           if "add" in custom_ingtype5[index1]: add_str = add_str + ', '.join(map(str, custom_ingtype5[index1]["add"])) + ", "
                           if "rem" in custom_ingtype1[index1]: rem_str = rem_str + ', '.join(map(str, custom_ingtype1[index1]["rem"])) + ", "
                           if "rem" in custom_ingtype2[index1]: rem_str = rem_str + ', '.join(map(str, custom_ingtype2[index1]["rem"])) + ", "
                           if "rem" in custom_ingtype3[index1]: rem_str = rem_str + ', '.join(map(str, custom_ingtype3[index1]["rem"])) + ", "
                           if "rem" in custom_ingtype4[index1]: rem_str = rem_str + ', '.join(map(str, custom_ingtype4[index1]["rem"])) + ", "
                           if "rem" in custom_ingtype5[index1]: rem_str = rem_str + ', '.join(map(str, custom_ingtype5[index1]["rem"])) + ", "
                           if (add_str=="" and rem_str==""):
                              if (myresult[j][1] == 'Regular'): dispatcher.utter_message("You can modify the quantity of {} in your order".format(item[0]))
                              else: dispatcher.utter_message("You can modify the quantity or size of {} in your order".format(item[0]))
                           else:
                              if (myresult[j][1] == 'Regular'): dispatcher.utter_message("You can modify the quantity or ingredients of {}".format(item[0]))
                              else: dispatcher.utter_message("You can modify the quantity size or ingredients of {}".format(item[0]))
                              if (add_str != ""):dispatcher.utter_message("The following ingredients can be added to your order of {}: {}".format(item[0],add_str))
                              if (rem_str != ""):dispatcher.utter_message("The following ingredients can be removed from your order of {}: {}".format(item[0],rem_str))
                           match_found = 1
                  if (match_found==0): dispatcher.utter_message("You do not have {} in your cart".format(item[0]))
               else:
                  dispatcher.utter_message("Please restate your order with a valid item name.To know whats on our menu, say MENU".format())
           else:
              dispatcher.utter_message("You do not have any items in your cart".format())
        else:
           dispatcher.utter_message("There are no such items on our menu. To know whats on our menu, say MENU".format())
        return[]

class ResetSlots(Action):
    def name(self) -> Text:
        return "reset_slots"
    def run(self,dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        print("Reset Slots")
        return[AllSlotsReset()]

class ResetItem(Action):
    def name(self) -> Text:
        return "reset_item"
    def run(self,dispatcher: CollectingDispatcher,tracker: Tracker,domain: Dict[Text, Any]) -> List[Dict]:
        return[SlotSet("item",None)]
