import requests
import numpy as np

def disclinker(discussionId, pageNo=1):
  #just a lil function to get the discussion api links
  pagestring = "http://discussion.theguardian.com/discussion-api/discussion//p/{}?pageSize=100&page={}".format(discussionId,pageNo)
  return pagestring


def discussionlinks(url):
  html = requests.get(url).text #get the article

  #the discusssion ID is hidden somewhere in a script so we need to find it with a little hack
  shorturlloc = int(html.find("shortUrlId"))
  discussionIdloc = shorturlloc + 16
  discussionId = html[discussionIdloc:discussionIdloc+5]
  print("Found discussion id {}".format(discussionId))

  #get the discussion and find out how many pages it has
  commentdict = requests.get(disclinker(discussionId)).json()
  pageamount = commentdict["pages"]
  commentcount = commentdict["discussion"]["commentCount"]
  threadcount = commentdict["discussion"]["topLevelCommentCount"]

  print("Found {} comments in {} threads over {} pages".format(commentcount,threadcount,pageamount))

  pagelist = [disclinker(discussionId,i+1) for i in range(pageamount)]

  return commentcount, threadcount, pagelist

def commentcleaner(comment):
  #I only need a small part of the info in each comment dict, so this is a function to extract that and make life easier

  commentid = comment["id"]
  text = comment["body"]
  points = comment["numRecommends"]
  parent = int(comment["responseTo"]["commentId"])
  
  cleancomment = {
    "id": commentid,
    "text": text,
    "points": points,
    "parent": parent}
  
  return cleancomment

def findParentChain(responses, current, topLevelId, idList):
  #I want to find the context of all responses with more than x upvotes
  parentId = current["parent"]
  if parentId == topLevelId:
    return idList
  else:
    idList.append(parentId)
    parent = next(response for response in responses if response["id"]==parentId)
    idList = findParentChain(responses, parent, topLevelId, idList)
  return idList

def embroidery(responses, parentId, commentarr, counter, level):
  #function to determine the thread level

  #we find the responses to the current comment
  responsesToParent = [item for item in responses if item["parent"]==parentId]

  #loop through them, add them to the output array, then call this function again with that comment as parent
  for response in responsesToParent:
    commentarr[counter,level] = str(response["points"]) + ": " + response["text"]
    counter += 1
    commentarr, counter = embroidery(responses, response["id"], commentarr, counter, level+1)
  
  return commentarr, counter

def threadhandler(thread, commentarr, counter, counterpoints, threshold):
  x = threshold #min point amount for us to count the comment
  #get parent info
  parentId = thread["id"]
  parentText = thread["body"]
  parentPoints = thread["numRecommends"]

  #clean the children and nab their points
  if "responses" in thread:
    responses = thread["responses"]
    cleanResponses = [commentcleaner(i) for i in responses]
    childpoints = [response["points"] for response in cleanResponses]
  else:
    childpoints = [0]

  #I want to check if the thread has any comments at all that have enough
  #points
  if parentPoints < x and all(point < x for point in childpoints):
    return commentarr, counter, counterpoints

  #add parent info to output array
  commentarr[counter, 0] = str(parentPoints) + ": " + parentText
  counter +=1
  counterpoints +=1

  if "responses" in thread and any(point >= x for point in childpoints):
    #find the Ids of the comments that have more than x points
    popComments = [response for response in cleanResponses if
                   response["points"]>=x] #select comments
    idList = [comment["id"] for comment in popComments]  #setting up list of ids
    counterpoints += len(idList)

    for i in popComments: #get any parents
      idList = findParentChain(cleanResponses, i, parentId, idList)
    
    #now we get the final lists of comments to embroider
    uniqueids = np.unique(np.array(idList)) #filter for duplicates
    finalcomments =  [response for response in cleanResponses if response["id"]
                      in uniqueids]

    #and embroider them, so they are nice and lned up in the output
    commentarr, counter = embroidery(finalcomments, parentId, commentarr, counter, 1)

  return commentarr, counter, counterpoints

if __name__ == "__main__":
  #get link from user
  link = input("which guardian article do you want the comments for? (link)")
  threshold = input("what is the minimum amoung of points you want them to have?")
  threshold = int(threshold) #bc apparenlty input is a string

  #get discussion info
  commentcount, threadcount, links = discussionlinks(link)

  #get all comment threads
  threads = []
  for link in links:
    page = requests.get(link).json()
    commentpage = page["discussion"]["comments"]
    threads.extend(commentpage)
  
  #set up info for making the output array
  comments = np.empty([commentcount, 220], dtype='object')
  counter = 0
  counterpoints = 0

  #add every thread to the output
  for thread in threads:
    comments, counter, counterpoints = threadhandler(thread, comments, counter,
                                                     counterpoints, threshold)
  print("{} comments with more than {} points".format(counterpoints,
                                                      threshold))  
  print("{} comments selected".format(counter))

  #and save
  comments[comments == None] = ""
  np.savetxt("comments.csv", comments, fmt='%s', delimiter='\t')
